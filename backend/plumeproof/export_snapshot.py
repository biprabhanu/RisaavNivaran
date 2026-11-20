"""
Write the offline snapshot used by the frontend when the backend is unreachable.

    cd backend && python -m plumeproof.export_snapshot

Output: frontend/src/lib/snapshot.json (Snapshot type in frontend/src/types/api.ts):
    {generated_at, meta, map, frames, evaluation}
Everything is computed in a scratch database; live state is untouched.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import db, replay
from .config import ACTIONS, ATTRIBUTION_THRESHOLD, DEFAULT_LAMBDA, HYPOTHESES, STATS, VERIFICATION_ACTION
from .kanjur import FACILITY, WIND
from .schemas import MapState, MetaResponse

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "snapshot.json"


def build_snapshot() -> dict:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="plumeproof-snapshot-")
    os.close(fd)
    try:
        with db.use_db(path):
            db.reset_db()
            frames = replay.run_full_replay()
            from app import _summary  # reuse the API's summary builder
            from .agent import CaseAgent

            cases = [_summary(CaseAgent(c)) for c in db.list_cases()]
            map_state = MapState(facility=FACILITY, observations=db.list_observations(), cases=cases, wind=WIND)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        from .scenarios import run_evaluation

        evaluation = run_evaluation().model_dump(mode="json")
    except Exception as exc:  # scenarios missing or failing: snapshot still useful
        print(f"warning: evaluation not included ({exc})", file=sys.stderr)
        evaluation = None
    meta = MetaResponse(hypotheses=HYPOTHESES, actions=ACTIONS, verification_action=VERIFICATION_ACTION,
                        default_lambda=DEFAULT_LAMBDA, attribution_threshold=ATTRIBUTION_THRESHOLD, stats=STATS)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": meta.model_dump(mode="json"),
        "map": map_state.model_dump(mode="json"),
        "frames": [f.model_dump(mode="json") for f in frames],
        "evaluation": evaluation,
    }


def main(out: Path = DEFAULT_OUT) -> None:
    snap = build_snapshot()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KiB, {len(snap['frames'])} frames, "
          f"evaluation={'yes' if snap['evaluation'] else 'no'})")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `import app` works
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT)
