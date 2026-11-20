"""Compute every engine number used in the Round 2 slides/speech/report from the real code.
Run: cd backend && source .venv/bin/activate && python ../round2_submission/slides/figures/src/compute_numbers.py"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../backend"))
from plumeproof import bayes, planner, verification, config
from plumeproof.schemas import Measurement, ActorType, DataLabel

P = config.DEFAULT_PRIOR
plan = planner.rank_actions(P, config.ACTIONS)
out = {"prior": P, "entropy": bayes.entropy(P), "lambda": config.DEFAULT_LAMBDA,
       "actions": [{"id": r.action_id, "label": r.label, "eig": r.eig_bits, "cost": r.cost_inr, "time": r.time_days,
                    "gain_per_10k": r.gain_per_10k, "score_per_10k": r.score_per_10k, "rank": r.rank} for r in plan.ranked]}
rec = config.ACTIONS_BY_ID["records_request"]
for prev in bayes.outcome_previews(P, rec):
    out[prev.outcome_id] = {"p": prev.probability, "posterior": prev.posterior, "entropy_after": prev.entropy_after}
c2 = config.ACTIONS_BY_ID
pre = Measurement(id="pre", rate_kg_h=1736, uncertainty_kg_h=434, date="2025-02-09", method="sat", independent=True,
                  actor=ActorType.SATELLITE, label=DataLabel.REAL_DATA)
post = Measurement(id="post", rate_kg_h=610, uncertainty_kg_h=150, date="2025-05-20", method="aerial", independent=True)
v = verification.evaluate_verification(pre, [post])
out["verification"] = {"verdict": v.verdict.value, "pre_low": v.pre_low, "pre_high": v.pre_high,
                       "post_low": v.post_low, "post_high": v.post_high,
                       "threshold": verification.recurrence_threshold(v)}
claim = post.model_copy(update={"id": "claim", "independent": False})
out["claim_only_verdict"] = verification.evaluate_verification(pre, [claim]).verdict.value
# replanning when OGI unavailable
from plumeproof.schemas import Constraints
p2 = planner.rank_actions(P, config.ACTIONS, Constraints(unavailable_resources=["ogi_inspector"], performed_actions=["records_request"]))
out["replan_ogi_unavailable"] = {"ranked": [r.action_id for r in p2.ranked], "excluded": [e.action_id for e in p2.excluded]}
json.dump(out, open(os.path.join(os.path.dirname(__file__), "numbers.json"), "w"), indent=2)
print(json.dumps(out, indent=1))
