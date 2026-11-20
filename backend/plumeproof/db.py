"""
SQLite persistence for PlumeProof (plain sqlite3, no ORM).

Every table stores one Pydantic model per row as JSON, plus a few indexed columns
(id, case_id, created order) so we can query cheaply. This keeps the schema trivially
in sync with ``schemas.py``: adding a field to a model needs no migration.

The database path comes from the env var PLUMEPROOF_DB (default backend/data/plumeproof.db).
A new connection is opened per call, which is safe for uvicorn's thread pool.

Production note: PostgreSQL/PostGIS is the intended production store (future work).
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Optional, TypeVar

from pydantic import BaseModel

from .schemas import ApprovalItem, ApprovalStatus, AuditEvent, Case, Observation, ToolCall

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "plumeproof.db"

T = TypeVar("T", bound=BaseModel)

# table name -> has a case_id column?
TABLES: dict[str, bool] = {
    "cases": False,
    "observations": True,
    "audit_events": True,
    "approvals": True,
    "tool_calls": True,
}


# Per-context override (used to run the replay in a scratch database without touching live state).
_DB_OVERRIDE: ContextVar[Optional[str]] = ContextVar("plumeproof_db_override", default=None)


def db_path() -> str:
    """Current database file path (override → env PLUMEPROOF_DB → default)."""
    return _DB_OVERRIDE.get() or os.environ.get("PLUMEPROOF_DB", str(DEFAULT_DB))


@contextmanager
def use_db(path: str) -> Iterator[None]:
    """Temporarily point every db call in this context at another database file."""
    token = _DB_OVERRIDE.set(path)
    try:
        yield
    finally:
        _DB_OVERRIDE.reset(token)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not exist."""
    with connect() as conn:
        for table, has_case in TABLES.items():
            case_col = "case_id TEXT," if has_case else ""
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                f" seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, {case_col} json TEXT NOT NULL)"
            )
        conn.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, json TEXT NOT NULL)")


def reset_db() -> None:
    """Drop and recreate every table (used by 'Reset demo')."""
    with connect() as conn:
        for table in list(TABLES) + ["kv"]:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    init_db()


def is_empty() -> bool:
    init_db()
    with connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM cases").fetchone()
    return n == 0


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def _put(table: str, model: BaseModel, case_id: Optional[str] = None) -> None:
    data = model.model_dump_json()
    model_id = getattr(model, "id")
    with connect() as conn:
        if TABLES[table]:
            conn.execute(
                f"INSERT INTO {table} (id, case_id, json) VALUES (?, ?, ?) "
                f"ON CONFLICT(id) DO UPDATE SET json = excluded.json, case_id = excluded.case_id",
                (model_id, case_id, data),
            )
        else:
            conn.execute(
                f"INSERT INTO {table} (id, json) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json",
                (model_id, data),
            )


def _get(table: str, model_id: str, cls: type[T]) -> Optional[T]:
    with connect() as conn:
        row = conn.execute(f"SELECT json FROM {table} WHERE id = ?", (model_id,)).fetchone()
    return cls.model_validate_json(row[0]) if row else None


def _list(table: str, cls: type[T], case_id: Optional[str] = None) -> list[T]:
    with connect() as conn:
        if case_id is not None and TABLES[table]:
            rows = conn.execute(f"SELECT json FROM {table} WHERE case_id = ? ORDER BY seq", (case_id,)).fetchall()
        else:
            rows = conn.execute(f"SELECT json FROM {table} ORDER BY seq").fetchall()
    return [cls.model_validate_json(r[0]) for r in rows]


def _delete_case_rows(case_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        for table, has_case in TABLES.items():
            if has_case:
                conn.execute(f"DELETE FROM {table} WHERE case_id = ?", (case_id,))


# ---------------------------------------------------------------------------
# Typed accessors
# ---------------------------------------------------------------------------
def save_case(case: Case) -> None:
    _put("cases", case)


def get_case(case_id: str) -> Optional[Case]:
    return _get("cases", case_id, Case)


def list_cases() -> list[Case]:
    return _list("cases", Case)


def delete_case(case_id: str) -> None:
    """Remove a case and everything attached to it (observations are kept, but unlinked)."""
    obs = list_observations(case_id)
    _delete_case_rows(case_id)
    for o in obs:  # observations are facts about the world: keep them, just unlink
        save_observation(o.model_copy(update={"case_id": None}))


def save_observation(obs: Observation) -> None:
    _put("observations", obs, obs.case_id)


def get_observation(obs_id: str) -> Optional[Observation]:
    return _get("observations", obs_id, Observation)


def list_observations(case_id: Optional[str] = None) -> list[Observation]:
    return _list("observations", Observation, case_id)


def add_event(event: AuditEvent) -> None:
    _put("audit_events", event, event.case_id)


def list_events(case_id: Optional[str] = None) -> list[AuditEvent]:
    return _list("audit_events", AuditEvent, case_id)


def save_approval(item: ApprovalItem) -> None:
    _put("approvals", item, item.case_id)


def get_approval(approval_id: str) -> Optional[ApprovalItem]:
    return _get("approvals", approval_id, ApprovalItem)


def list_approvals(case_id: Optional[str] = None, status: Optional[ApprovalStatus] = None) -> list[ApprovalItem]:
    items = _list("approvals", ApprovalItem, case_id)
    return [i for i in items if status is None or i.status == status]


def add_tool_call(call: ToolCall) -> None:
    _put("tool_calls", call, call.case_id)


def list_tool_calls(case_id: Optional[str] = None) -> list[ToolCall]:
    return _list("tool_calls", ToolCall, case_id)


def kv_get(key: str) -> Optional[Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT json FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def kv_set(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO kv (key, json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET json = excluded.json",
            (key, json.dumps(value)),
        )


def kv_delete(key: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM kv WHERE key = ?", (key,))
