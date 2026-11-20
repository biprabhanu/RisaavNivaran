"""The Kanjur 2025–2026 historical replay."""
from plumeproof import db, replay
from plumeproof.schemas import CaseStatus as S, DataLabel


def test_full_replay(temp_db):
    frames = replay.run_full_replay()
    assert len(frames) == replay.TOTAL_STEPS + 1 <= 13
    assert frames[0].case is None and frames[-1].done

    by_id = {f.step_id: f for f in frames}
    # Step 1: real observation
    assert by_id["obs-2025"].label == DataLabel.REAL_DATA
    assert {t.tool.value for t in by_id["obs-2025"].tool_calls} >= {"query_observations", "overlay_facility_zones"}
    # Step 3: records request first + approval pending
    plan = by_id["plan"].plan
    assert plan.ranked[0].action_id == "records_request"
    assert by_id["plan"].pending_approval is not None
    # OGI unavailable → excluded before ranking, re-ranked
    ogi = by_id["ogi-unavailable"]
    assert "ogi_survey" in {e.action_id for e in ogi.plan.excluded}
    assert "ogi_survey" in {r.action_id for r in ogi.plan_before.ranked}
    assert ogi.banner.kind == "warning"
    # Records: fault found → posterior ≈ gas 65 / flare 29 / waste 6
    post = by_id["records-fault"].belief_after
    assert abs(post["gas_collection"] - 0.65) < 0.02 and abs(post["waste_surface"] - 0.06) < 0.02
    # Repair claim → REJECTED
    rej = by_id["repair-claim"]
    assert rej.banner.kind == "rejected" and "REJECTED" in rej.banner.title
    assert rej.case.case.status == S.VERIFICATION_PENDING
    assert any(e.type == "TRANSITION_REJECTED" for e in rej.new_events)
    # Follow-up measurement → verified, then closure approved
    assert by_id["follow-up"].verification.verdict.value == "VERIFIED_REDUCTION"
    assert by_id["closure"].case.case.status == S.VERIFIED_REDUCTION
    # 2026 real observation → reopened as recurring
    last = frames[-1]
    c = last.case.case
    assert c.status == S.RECURRING and c.reopen_count == 1
    assert last.banner.kind == "reopened"
    types = [e.type for e in last.timeline]
    assert "CASE_REOPENED" in types
    assert any(e.data.get("to") == "RECURRING" for e in last.timeline if e.type == "STATUS_CHANGED")


def test_step_without_auto_approve_waits(temp_db):
    replay.reset()
    for _ in range(3):
        f = replay.step()
    assert f.pending_approval is not None
    same = replay.step(auto_approve=False)
    assert same.step_index == f.step_index
    nxt = replay.step(auto_approve=True)
    assert nxt.step_index == f.step_index + 1
    assert any(e.label == DataLabel.HUMAN_DECISION and e.actor_name == replay.PRESENTER for e in nxt.new_events)


def test_scratch_replay_does_not_touch_live_state(temp_db):
    replay.reset()
    replay.step()
    frames = replay.frames_in_scratch_db()
    assert len(frames) == replay.TOTAL_STEPS + 1
    assert db.kv_get(replay.KV_KEY)["step"] == 1


def test_manual_approval_then_step_advances_past_follow_up_approval():
    """Regression: approving the framed item by hand must let the replay advance even when the agent
    immediately queues a follow-up approval (attribution approved → notification pending)."""
    from plumeproof import db, replay
    from plumeproof.agent import CaseAgent
    from plumeproof.schemas import ApprovalDecision

    replay.reset()
    frame = replay.step()
    while frame.pending_approval is None or frame.pending_approval.kind.value != "SOURCE_ATTRIBUTION":
        frame = replay.step()
    idx = frame.step_index
    CaseAgent.load(replay.CASE_ID).decide(frame.pending_approval.id, ApprovalDecision(decision="approve"))
    nxt = replay.step(auto_approve=False)
    assert nxt.step_index == idx + 1
    # The newly queued notification is now the frame's pending item, and manual stepping waits for it.
    assert nxt.pending_approval is not None and nxt.pending_approval.kind.value == "NOTIFICATION"
    assert replay.step(auto_approve=False).step_index == idx + 1


def test_rejected_approval_does_not_advance_and_is_reproposed():
    """Human-in-the-loop is real: a Reject must stop the script, not be narrated as an approval."""
    from plumeproof import db, replay
    from plumeproof.agent import CaseAgent
    from plumeproof.schemas import ApprovalDecision, ApprovalStatus

    replay.reset()
    frame = replay.step()
    while frame.pending_approval is None:
        frame = replay.step()
    idx, status_before = frame.step_index, frame.case.case.status
    rejected_id = frame.pending_approval.id
    CaseAgent.load(replay.CASE_ID).decide(rejected_id, ApprovalDecision(decision="reject"))
    nxt = replay.step(auto_approve=False)
    assert nxt.step_index == idx                     # the script did not advance
    assert nxt.banner is not None and "REJECTED" in nxt.banner.title
    assert nxt.case.case.status == status_before     # the agent did not act
    assert nxt.pending_approval is not None and nxt.pending_approval.id != rejected_id
    assert db.get_approval(rejected_id).status == ApprovalStatus.REJECTED
    # Approving the re-proposed item continues the replay normally.
    after = replay.step(auto_approve=True)
    assert after.step_index == idx + 1


def test_replay_ends_visibly_recurring():
    from plumeproof import replay
    frames = replay.run_full_replay()
    assert frames[-1].done and frames[-1].case.case.status.value == "RECURRING"
    assert frames[-1].case.case.reopen_count == 1
