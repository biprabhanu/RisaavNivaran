"""Shared pytest fixtures: every test that touches the database gets its own temporary SQLite file."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `import app` works from tests


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point PLUMEPROOF_DB at a fresh temp file and create the tables."""
    from plumeproof import db

    path = tmp_path / "test.db"
    monkeypatch.setenv("PLUMEPROOF_DB", str(path))
    db.reset_db()
    return path


@pytest.fixture()
def client(temp_db, monkeypatch):
    """FastAPI TestClient on a seeded temp database, with the LLM forced off (template mode)."""
    from fastapi.testclient import TestClient

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import app as app_module

    app_module.seed_demo()
    with TestClient(app_module.app) as c:
        yield c
