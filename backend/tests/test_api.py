"""HTTP API (FastAPI TestClient on a seeded temporary database, template mode)."""
CASE = "/api/cases/KJ-2025-02"


def test_health_meta(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["llm_mode"] == "template"
    meta = client.get("/api/meta").json()
    assert [x["id"] for x in meta["hypotheses"]] == ["waste_surface", "gas_collection", "flare"]
    assert len(meta["actions"]) == 4 and meta["stats"]["response_rate_pct"] == 13


def test_seeded_cases_and_map(client):
    cases = client.get("/api/cases").json()
    assert any(c["id"] == "KJ-2025-02" for c in cases)
    detail = client.get(CASE).json()
    assert detail["case"]["reopen_count"] == 1 and detail["plan"]["ranked"]
    m = client.get("/api/map").json()
    assert len(m["facility"]["zones"]) == 3 and m["wind"]["illustrative"] is True
    assert {o["id"] for o in m["observations"]} >= {"OBS-2025-02-09-A", "OBS-2026-04-03"}
    assert client.get("/api/cases/NOPE").status_code == 404


def test_plan_lambda_and_constraints(client):
    p0 = client.get(f"{CASE}/plan", params={"lam": 0}).json()
    p1 = client.get(f"{CASE}/plan", params={"lam": 20000}).json()
    assert p0["lam"] == 0 and p1["lam"] == 20000
    assert p0["ranked"][0]["action_id"] == "records_request"
    cons = client.get(CASE).json()["case"]["constraints"]
    cons["unavailable_resources"] = ["ogi_inspector"]
    plan = client.put(f"{CASE}/constraints", json=cons).json()
    assert "ogi_survey" in {e["action_id"] for e in plan["excluded"]}
    assert "ogi_survey" not in {r["action_id"] for r in plan["ranked"]}
    tl = client.get(f"{CASE}/timeline").json()
    assert tl[-2]["type"] == "CONSTRAINTS_UPDATED" or any(e["type"] == "CONSTRAINTS_UPDATED" for e in tl)


def test_draft_template_and_notice_approval(client):
    r = client.post(f"{CASE}/draft", json={"kind": "notice"}).json()
    assert r["mode"] == "template" and "requires human approval" in r["text"].lower()
    pending = client.get("/api/approvals", params={"status": "PENDING"}).json()
    notice = [a for a in pending if a["payload"].get("purpose") == "notice"]
    assert notice
    decided = client.post(f"/api/approvals/{notice[0]['id']}/decide", json={"decision": "approve"}).json()
    assert decided["status"] == "APPROVED"
    again = client.post(f"/api/approvals/{notice[0]['id']}/decide", json={"decision": "approve"})
    assert again.status_code == 409
    for kind in ("ranking_explanation", "case_summary"):
        assert client.post(f"{CASE}/draft", json={"kind": kind}).json()["mode"] == "template"


def test_request_transition_rejected(client):
    d = client.post(f"{CASE}/request-transition", json={"to_status": "VERIFIED_REDUCTION", "actor": "human"}).json()
    assert d["allowed"] is False and "REJECTED" in d["reason"]
    tl = client.get(f"{CASE}/timeline").json()
    assert tl[-1]["type"] == "TRANSITION_REJECTED"


def test_verification_and_whatif(client):
    pre = {"id": "p", "rate_kg_h": 1736, "uncertainty_kg_h": 434, "date": "2025-02-09", "method": "sat", "independent": True}
    post = {"id": "q", "rate_kg_h": 610, "uncertainty_kg_h": 150, "date": "2025-05-20", "method": "aerial", "independent": True}
    v = client.post("/api/verification/evaluate", json={"pre": pre, "posts": [post]}).json()
    assert v["verdict"] == "VERIFIED_REDUCTION"
    claim = dict(post, id="c", independent=False)
    v = client.post("/api/verification/evaluate", json={"pre": pre, "posts": [claim]}).json()
    assert v["verdict"] == "NO_INDEPENDENT_EVIDENCE"
    w = client.post("/api/whatif", json={"action_id": "records_request", "outcome_id": "fault_found"}).json()
    assert abs(w["update"]["posterior"]["gas_collection"] - 0.65) < 0.02
    assert abs(w["eig_bits"] - 0.50) < 0.02
    assert client.post("/api/whatif", json={"action_id": "records_request", "outcome_id": "x"}).status_code == 422


def test_replay_reset_and_step_to_done(client):
    script = client.get("/api/replay/script").json()
    f = client.post("/api/replay/reset").json()
    assert f["step_index"] == 0 and f["case"] is None
    assert client.get(CASE).status_code == 404  # case removed by reset
    for _ in range(len(script)):
        f = client.post("/api/replay/step", json={"auto_approve": True}).json()
    assert f["done"] and f["banner"]["kind"] == "reopened"
    # Stepping past the end is harmless
    assert client.post("/api/replay/step", json={}).json()["done"]
    frames = client.get("/api/replay/frames").json()
    assert len(frames) == len(script) + 1


def test_replay_manual_approval_via_queue(client):
    client.post("/api/replay/reset")
    for _ in range(3):
        f = client.post("/api/replay/step", json={"auto_approve": False}).json()
    item = f["pending_approval"]
    assert item and item["kind"] == "NOTIFICATION"
    assert client.post("/api/replay/step", json={"auto_approve": False}).json()["step_index"] == 3
    client.post(f"/api/approvals/{item['id']}/decide", json={"decision": "edit", "edited_text": "Edited letter"})
    f = client.post("/api/replay/step", json={"auto_approve": False}).json()
    assert f["step_index"] == 4 and f["case"]["case"]["status"] == "INVESTIGATION_REQUESTED"


def test_measurement_endpoint(client):
    client.post("/api/replay/reset")
    for _ in range(8):  # up to the rejected repair claim
        f = client.post("/api/replay/step", json={}).json()
    assert f["case"]["case"]["status"] == "VERIFICATION_PENDING"
    m = {"id": "M-api", "rate_kg_h": 500, "uncertainty_kg_h": 100, "date": "2025-05-01", "method": "aerial", "independent": True}
    d = client.post(f"{CASE}/measurements", json=m).json()
    assert d["case"]["verification"]["verdict"] == "VERIFIED_REDUCTION"
    assert any(a["kind"] == "FINAL_CLOSURE" for a in d["pending_approvals"])


def test_demo_reset_and_upload(client):
    client.post("/api/replay/reset")
    assert client.post("/api/demo/reset").json() == {"status": "ok"}
    assert client.get(CASE).json()["case"]["reopen_count"] == 1
    up = {"observation_id": "OBS-UP-1", "facility_name": "Test Landfill", "latitude": 18.5, "longitude": 73.8,
          "observation_date": "2026-05-12", "emission_rate_kg_hour": 1450.5}
    d = client.post("/api/observations/upload", json=up).json()
    assert d["case"]["status"] == "SOURCE_ATTRIBUTION_PENDING" and d["observations"][0]["label"] == "SIMULATED EVENT"
    assert client.post("/api/observations/upload", json=up).status_code == 409
    assert len(client.get("/api/audit").json()) > 20


def test_spa_fallback_and_docs(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/api/does-not-exist").status_code == 404


def test_evaluate_endpoints(client):
    r = client.post("/api/evaluate", json={"seed": 2026, "n_scenarios": 25}).json()
    pol = {p["policy_id"]: p for p in r["policies"]}
    assert pol["C"]["false_closures"] == 0 and r["n_scenarios"] == 25
    latest = client.get("/api/evaluate/latest").json()
    assert latest["generated_at"] == r["generated_at"]
