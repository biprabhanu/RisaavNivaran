# PlumeProof demo script

> Before you start: open the deployed site and click **Reset demo** (top-right). Check that the LLM badge shows either "LLM: on" or "LLM: off (template mode)". Both work.

## A. 3-minute live demo (click by click)

The replay has 11 steps and never advances on its own unless you press Play. When an approval card is showing, click **Approve**: that click is the human decision, and the replay advances. In Play mode, approvals are taken as the presenter's click automatically.


| Time | Click | Say |
|---|---|---|
| 0:00 | **Landing page** | "5,000+ UN methane alerts, and only 13% get a response. Detection is solved; follow-through isn't. PlumeProof is an agent that turns an alert into a managed case and refuses to close it without evidence. Input: satellite plumes. Output: a ranked investigation plan, approval-gated actions and a verified verdict. Users: landfill operators, pollution control boards, UN IMEO/MARS focal points." |
| 0:20 | **Start live demo**, which opens Replay and resets the case | "This is a replay of real Carbon Mapper observations at Kanjur landfill, Mumbai. Real data is tagged blue; simulated operational events are tagged amber." |
| 0:30 | **Next** (step 1/11: real obs, 9 Feb 2025) | "Two real plumes: 1,600 and 136 kg/h. The agent opens case KJ-2025-02 and calls `overlay_facility_zones` to find who is accountable: BMC SWM, the operator, and MPCB." |
| 0:45 | **Next** (step 2: hypotheses) | "It keeps three competing hypotheses, waste surface 50%, gas collection 35%, flare 15%, an uncertainty of 1.44 bits. It doesn't guess." |
| 1:00 | **Next** (step 3: planner), then **Approve** (step 4: request sent) | "It computes expected information gain for each investigation. The ground survey is the most informative, 0.91 bits, but costs ₹60k. The records request gives 0.50 bits for ₹2k, so it ranks first. A human approves; the agent never acts alone." |
| 1:20 | **Next** (step 5: OGI unavailable) | "Simulated: the gas-imaging inspector is unavailable. The agent excludes that action *before* ranking, re-plans, and explains the trade-off." |
| 1:35 | **Next** (step 6: records show a fault), then **Approve** attribution (step 7) | "Bayes' rule: the gas-collection system jumps to 65% and the waste surface falls to 6%. That posterior is computed live, not typed in." |
| 1:55 | **Approve** the notice (step 8: repair claim) | **Pause on the red banner.** "The operator says it's fixed and asks to close. The agent says **no**: no independent post-intervention measurement. A claim is not evidence. This is where alert systems and checklists record a false closure." |
| 2:15 | **Next** (step 9: follow-up measurement), then **Approve** closure (step 10) | "An independent measurement arrives: 610 ± 150 kg/h. Its upper bound is below the lower bound of the pre-repair interval, so it's a verified reduction. A human approves closure." |
| 2:30 | **Next** (step 11: real obs, 3 Apr 2026) | "Real: 3,300 kg/h, fourteen months later. The agent reopens the case as Recurring, automatically. Persistence over months is why this needs an agent." |
| 2:45 | **Evaluation** tab | "Across 25 seeded scenarios, alert-only and checklist policies close cases on unsupported claims; PlumeProof has zero false closures and needs fewer inspections than the checklist. These numbers come from running the simulation; click Re-run and they regenerate." |
| (Q&A) | **Case page → Try to close case** | Shows the guardrail live: the state machine rejects closure with a reason. |
| (Q&A) | **Planner → λ slider / Mark unavailable** | The ranking recomputes live, and excluded actions show their reasons. |
| (Q&A) | **What-if** | Pick any action and outcome and watch Bayes' rule update the beliefs. |
| 3:00 | End | "Every plume deserves an investigation. Every claimed fix deserves evidence." |

Backup: if the site is unreachable, the frontend replays from the bundled snapshot. The banner "Offline snapshot mode" appears, and everything else looks the same.

## B. 60-second product video script

| Sec | Visual | Voice-over |
|---|---|---|
| 0–8 | NASA EMIT plume image → Landing page stat "13%" | "Satellites now spot methane leaks from space. But only 13% of UN alerts ever get a response." |
| 8–18 | Replay step 1–2: map, plumes, belief bars | "PlumeProof turns each alert into a case. Real Kanjur landfill data, three competing source hypotheses." |
| 18–30 | Step 3–4: planner table, OGI struck out | "It picks the investigation that buys the most information per rupee and per day, and re-plans when a resource drops out. Humans approve every critical step." |
| 30–42 | Step 6: red REJECTED banner | "When the operator claims the leak is fixed, PlumeProof refuses to close the case without an independent measurement." |
| 42–52 | Step 7–8: interval chart, REOPENED banner | "It verifies the reduction with uncertainty, and reopens the case automatically when emissions return." |
| 52–60 | Evaluation chart: false closures A/B vs C = 0 | "Zero false closures across 25 scenarios. PlumeProof: from satellite alert to verified mitigation." |

## C. 10 likely judge questions

1. **Why agentic and not a checklist?** A checklist runs the same steps in the same order for every case. PlumeProof keeps state for months, revises its beliefs with each piece of evidence, picks its next action by information value, re-plans when a resource disappears, refuses unsupported closure, and reopens a case on recurrence. In our evaluation the fixed checklist needs more inspections per resolved case, and it closes cases on repair claims.
2. **Where do the likelihoods come from?** They are illustrative demonstration values, chosen so that the computed results reproduce our proposal's worked example (see ASSUMPTIONS.md). The ±20% sensitivity analysis shows the top-ranked action is stable. In production they would be calibrated with environmental engineers and updated from case outcomes, since every closed case is labelled data.
3. **What if the LLM hallucinates?** The LLM can't change anything. All maths, rankings, verdicts and state transitions are deterministic, tested Python. The LLM only drafts text, and a human approves every outgoing notice. When it "requests" a transition, the state machine validates it against the rules. With no API key, the whole app runs on templates.
4. **How does this scale to 5,000 alerts?** Each case is an independent, cheap state machine: the maths is microseconds per case. The planner ranks *where human attention goes*. The approval queue and deadline tracking are what let a small team supervise thousands of cases. Postgres/PostGIS and a task queue would be the production path.
5. **Why not just use satellite data for verification?** UNEP itself notes satellites alone can't confirm mitigation. A missed detection might be clouds, wind or detection limits. Revisits are weeks apart and have large uncertainty. So we require an independent post-intervention measurement with an uncertainty interval, under comparable conditions. A later satellite pass still triggers reopening.
6. **Privacy and legal notification concerns?** Notices go only to the public bodies and operators responsible for a facility. The agent drafts and a human sends (simulated in the demo). Every decision is logged with its evidence, and the data is facility-level emissions data, not personal data. Jurisdiction mapping would be configured with the regulator.
7. **What if two measurements disagree?** Both are kept, and the verdict is INCONCLUSIVE. The agent requests another measurement rather than picking the convenient one.
8. **How do you handle an operator who never replies?** `track_deadline` flags overdue tasks. The agent escalates, treats the action as failed (no belief update), and re-ranks the remaining options.
9. **What's real and what's simulated?** The Carbon Mapper plume observations (9 Feb 2025, 3 Apr 2026) are real. Stakeholder responses, inspector availability, records content, repair claims and the follow-up measurement are simulated and labelled as such on every screen.
10. **What's the role of λ?** λ converts days into rupees, the cost of delay. A high λ favours fast actions; λ = 0 ranks on money alone. The slider shows the ranking is robust across a wide range.
