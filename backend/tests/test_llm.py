"""
The optional Claude drafting path, tested with a fake client (no network, no API key needed).

Rules being checked:
  * no key (or a blank key, or a missing SDK) → template mode
  * key + good response → mode "llm" with the model recorded
  * any failure (exception, refusal, truncation, empty text) → silent fallback to the template
  * the prompt carries only the facts we passed in
  * an LLM-suggested status change goes through the state machine and can be rejected
"""
from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from plumeproof import db, kanjur, llm
from plumeproof.agent import CaseAgent
from plumeproof.schemas import ActorType, CaseStatus as S, TransitionRequest

CTX = {
    "case_id": "KJ-2025-02",
    "facility_name": "Kanjur Landfill",
    "recipient": "Kanjur landfill operator",
    "observations": ["9 Feb 2025: Plume A ~1600 kg/h (REAL DATA)", "9 Feb 2025: Plume B ~136 kg/h (REAL DATA)"],
    "deadline": "within 1 working day",
}


# ---------------------------------------------------------------------------
# Fake Anthropic client
# ---------------------------------------------------------------------------
class FakeMessages:
    def __init__(self, owner: "FakeClient"):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        if self.owner.raise_exc is not None:
            raise self.owner.raise_exc
        return self.owner.response


class FakeClient:
    def __init__(self, text="Dear operator, please send the records.", stop_reason="end_turn", raise_exc=None,
                 extra_blocks=()):
        self.calls: list[dict] = []
        self.raise_exc = raise_exc
        blocks = [*extra_blocks, SimpleNamespace(type="text", text=text)]
        self.response = SimpleNamespace(content=blocks, stop_reason=stop_reason, model="fake-model")
        self.messages = FakeMessages(self)
        self.beta = SimpleNamespace(messages=FakeMessages(self))


@pytest.fixture()
def with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)


def install(monkeypatch, client: FakeClient) -> FakeClient:
    monkeypatch.setattr(llm, "_make_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def test_template_mode_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.llm_mode() == "template"
    assert llm.llm_model() is None
    result = llm.draft("notice", CTX)
    assert result.mode == "template" and result.model is None
    assert "KJ-2025-02" in result.text and "human approval" in result.text


def test_blank_key_means_template_mode(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    assert llm.llm_mode() == "template"


def test_missing_sdk_means_template_mode(monkeypatch, with_key):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("no anthropic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert llm.llm_mode() == "template"


def test_model_is_env_overridable(monkeypatch, with_key):
    assert llm.llm_model() == llm.DEFAULT_MODEL
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    assert llm.llm_model() == "claude-opus-5-5"


# ---------------------------------------------------------------------------
# Drafting with the fake client
# ---------------------------------------------------------------------------
def test_llm_mode_returns_claude_text(monkeypatch, with_key):
    fake = install(monkeypatch, FakeClient(text="Formal letter text."))
    result = llm.draft("notice", CTX)
    assert result.mode == "llm"
    assert result.text == "Formal letter text."
    assert result.model == "fake-model"
    assert len(fake.calls) == 1


def test_current_gen_model_uses_fallbacks_and_low_effort(monkeypatch, with_key):
    fake = install(monkeypatch, FakeClient())
    llm.draft("case_summary", CTX)
    call = fake.calls[0]
    assert call["model"] == llm.DEFAULT_MODEL
    assert call["betas"] == [llm.FALLBACK_BETA] and call["fallbacks"] == "default"
    assert call["output_config"] == {"effort": "low"}
    assert call["system"] == llm.SYSTEM_PROMPT


def test_older_model_gets_plain_request(monkeypatch, with_key):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    fake = install(monkeypatch, FakeClient())
    result = llm.draft("notice", CTX)
    call = fake.calls[0]
    assert result.mode == "llm"
    assert "fallbacks" not in call and "betas" not in call and "output_config" not in call


def test_thinking_blocks_are_skipped(monkeypatch, with_key):
    install(monkeypatch, FakeClient(text="Only this.", extra_blocks=[SimpleNamespace(type="thinking", thinking="")]))
    assert llm.draft("notice", CTX).text == "Only this."


def test_prompt_contains_only_given_facts(monkeypatch, with_key):
    fake = install(monkeypatch, FakeClient())
    llm.draft("notice", CTX)
    user_msg = fake.calls[0]["messages"][0]["content"]
    assert fake.calls[0]["messages"][0]["role"] == "user"
    for needle in ("KJ-2025-02", "1600 kg/h", "136 kg/h", "Kanjur Landfill", "within 1 working day"):
        assert needle in user_msg
    # The system prompt forbids inventing facts.
    assert "Never invent numbers" in fake.calls[0]["system"]


@pytest.mark.parametrize("fake", [
    FakeClient(raise_exc=TimeoutError("API timed out")),
    FakeClient(raise_exc=RuntimeError("500 server error")),
    FakeClient(stop_reason="refusal"),
    FakeClient(stop_reason="max_tokens", text="Dear operator, please"),
    FakeClient(text="   "),
], ids=["timeout", "api-error", "refusal", "truncated", "empty"])
def test_any_failure_falls_back_to_template(monkeypatch, with_key, fake):
    install(monkeypatch, fake)
    result = llm.draft("notice", CTX)
    assert result.mode == "template" and result.model is None
    assert result.text == llm.template_notice(CTX)


def test_allow_llm_false_never_calls_client(monkeypatch, with_key):
    fake = install(monkeypatch, FakeClient())
    assert llm.draft("notice", CTX, allow_llm=False).mode == "template"
    assert fake.calls == []


# ---------------------------------------------------------------------------
# LLM suggestions can only REQUEST transitions
# ---------------------------------------------------------------------------
@pytest.fixture()
def agent(temp_db):
    for o in kanjur.REAL_OBSERVATIONS:
        db.save_observation(o)
    a = CaseAgent.open_case("L-1", "LLM guardrail case", kanjur.FACILITY, [kanjur.OBS_2025_A, kanjur.OBS_2025_B],
                            kanjur.STAKEHOLDERS, pre_measurement=kanjur.PRE_MEASUREMENT, sim_date="2025-02-09")
    a.initialise_hypotheses()
    return a


def test_template_mode_suggests_nothing(agent, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.suggest_transition(agent.case) is None
    assert llm.apply_suggestion(agent, None) is None


def test_illegal_llm_suggestion_is_rejected_and_logged(agent):
    agent.case.status = S.REPAIR_REPORTED
    agent.save()
    agent = CaseAgent.load("L-1")
    suggestion = TransitionRequest(to_status=S.VERIFIED_REDUCTION, actor=ActorType.AGENT,
                                   reason="Operator says it is fixed", requested_by_llm=True)

    decision = llm.apply_suggestion(agent, suggestion)

    assert decision is not None and decision.allowed is False
    assert CaseAgent.load("L-1").case.status == S.REPAIR_REPORTED  # unchanged
    rejected = [e for e in db.list_events("L-1") if e.type == "TRANSITION_REJECTED"]
    assert rejected, "the rejection must be in the audit log"
    assert rejected[-1].data.get("requested_by_llm") is True


def test_legal_llm_suggestion_still_goes_through_validator(agent):
    # SOURCE_ATTRIBUTION_PENDING → INVESTIGATION_REQUESTED needs human approval, so the LLM cannot do it alone.
    suggestion = TransitionRequest(to_status=S.INVESTIGATION_REQUESTED, actor=ActorType.AGENT, requested_by_llm=True)
    decision = llm.apply_suggestion(agent, suggestion)
    assert decision is not None and decision.allowed is False and decision.requires_approval is not None
    assert CaseAgent.load("L-1").case.status == S.SOURCE_ATTRIBUTION_PENDING


# ---------------------------------------------------------------------------
# Health badge
# ---------------------------------------------------------------------------
def test_health_reports_template_mode(client):
    body = client.get("/api/health").json()
    assert body["llm_mode"] == "template" and body["llm_model"] is None


def test_health_reports_llm_mode_with_key(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    body = client.get("/api/health").json()
    assert body["llm_mode"] == "llm" and body["llm_model"] == llm.DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Template "Explain this ranking" must add value beyond plan.explanation
# ---------------------------------------------------------------------------
def _plan(**constraints):
    from plumeproof import config, planner
    from plumeproof.schemas import Constraints

    return planner.rank_actions(config.DEFAULT_PRIOR, config.ACTIONS, Constraints(**constraints), config.DEFAULT_LAMBDA)


def test_template_ranking_explanation_shows_arithmetic_and_differs():
    plan = _plan()
    text = llm.template_ranking_explanation({"plan": plan, "explanation": plan.explanation})
    assert text != plan.explanation
    top = plan.ranked[0]
    assert top.action_id == "records_request"
    # The top action's arithmetic, built from the plan's own numbers.
    expected = (f"score = {top.eig_bits:.2f} bits ÷ (₹2,000 + ₹1,000/day × 1 day = ₹3,000) "
                f"= {top.score_per_10k:.2f} bits per ₹10k-equivalent")
    assert expected in text
    assert "1.66 bits per ₹10k-equivalent" in text  # 0.4994 / 3,000 × 10,000
    # What would change the decision: the no-fault branch (PDF: waste ≈ 84%).
    assert "Exposed waste surface rises to 84%" in text
    assert "becomes the next best" in text


def test_template_ranking_explanation_lists_exclusions_with_reasons():
    plan = _plan(unavailable_resources=["ogi_inspector"])
    text = llm.template_ranking_explanation({"plan": plan})
    assert "Excluded before ranking" in text
    assert "Resource unavailable: OGI inspector" in text
    assert "#2 Comprehensive ground-level survey" in text


def test_ranking_draft_without_plan_still_richer_than_explanation(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ctx = {"explanation": "Recommended: records.", "ranked_actions": "#1 Records: EIG 0.50 bits",
           "excluded_actions": "none"}
    text = llm.draft("ranking_explanation", ctx).text
    assert text != ctx["explanation"] and "EIG ÷ (cost + λ × time)" in text


def test_plan_object_is_not_dumped_into_llm_prompt(monkeypatch, with_key):
    fake = install(monkeypatch, FakeClient())
    plan = _plan()
    llm.draft("ranking_explanation", {"plan": plan, "case_id": "KJ-2025-02"})
    msg = fake.calls[0]["messages"][0]["content"]
    assert "plan: " not in msg and "RankedAction(" not in msg
    assert "1.66 bits per ₹10k-equivalent" in msg  # the arithmetic reaches Claude through the reference template
