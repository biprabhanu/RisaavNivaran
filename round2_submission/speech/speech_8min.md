# PlumeProof: Round 2 speech (8 minutes)

**Speakers:** **Bipra** (lead: problem, agent design, novelty, results) and **Mandar** (data pipeline, dashboard, live demo).
**Total:** 7:30 of planned content plus a 30-second buffer, so 8:00. The live part (video plus demo) is 3:45.
**Pace:** calm and clear, about 140 words a minute (the slide sections are about 520 words, about 3:45; the demo lines are about 230 words plus clicks). Every number below matches the slides and the report. Each one comes from the running code or from our proposal PDF.

**Cues:** **[CLICK NEXT]** means next slide. **[SWITCH TO BROWSER]** and **[BACK TO SLIDES]** are for Mandar's laptop. *(Italics)* are stage directions, so don't read them aloud.

| # | Slide | Speaker | Time | Clock at end |
|---|---|---|---|---|
| 1 | Title | Bipra | 0:15 | 0:15 |
| 2 | Video (60 s) | (video) | 1:00 | 1:15 |
| 3 | Problem | Bipra | 0:25 | 1:40 |
| 4 | Kanjur test case | Mandar | 0:20 | 2:00 |
| 5 | What PlumeProof does | Bipra | 0:28 | 2:28 |
| 6 | Why agentic | Bipra | 0:20 | 2:48 |
| 7 | Novelty 1: information gain | Bipra | 0:28 | 3:16 |
| 8 | Novelty 2: a claim is not evidence | Bipra | 0:24 | 3:40 |
| 9 | Architecture | Mandar | 0:20 | 4:00 |
| 10 | Live demo | Mandar | 2:45 | 6:45 |
| 11 | Results | Bipra | 0:30 | 7:15 |
| 12 | Impact, limits, thank you | Bipra | 0:15 | 7:30 |
| | Buffer | | 0:30 | 8:00 |

---

## Slide 1: Title (Bipra, 0:15)

> Good morning. We are Team RisaavNivaran from IIT Bombay. I am Bipra, and this is Mandar. Our project is **PlumeProof**. It takes satellite methane alerts and follows each one through to a **verified** fix. First, a sixty-second video.

**[CLICK NEXT]**

## Slide 2: Video (1:00)

*(Click play. Don't talk over it. If the video fails, skip it and say: "We'll show all of this live in a moment.")*

**[CLICK NEXT]**

## Slide 3: Problem (Bipra, 0:25)

> Satellites can now see methane leaks from space. The UN has sent **more than 5,000 alerts**, but only **13 percent** get a response. The target is **80 percent** by 2030.
> So detection is solved. Follow-through is not. After an alert, nobody owns the case. Who is responsible? What do we check first? Was the fix real? Did the leak come back?

**[CLICK NEXT]**

## Slide 4: Kanjur test case (Mandar, 0:20)

> Our test case is **Kanjur landfill in Mumbai**, one of the world's three largest methane sources. Real Carbon Mapper data: in February 2025, plumes of about **1,600** and **136** kilograms per hour; in April 2026, about **3,300**. Three possible sources: waste surface, gas pipes, or flare. Operational events are simulated and labelled.

**[CLICK NEXT]**

## Slide 5: What PlumeProof does (Bipra, 0:28)

> **Input:** a satellite plume and the facility map. **The agent** keeps three competing hypotheses, chooses the best next investigation, and drafts notices. **A human approves** every critical step. **Output:** a verified result with uncertainty and a full audit trail. If the plume returns, the case reopens by itself.
> Our users are regulators, city authorities, landfill operators and UN focal points.

**[CLICK NEXT]**

## Slide 6: Why agentic (Bipra, 0:20)

> Why an agent? A case lasts months. A checklist repeats fixed steps and closes when the operator says "fixed". Our agent remembers the case, updates its beliefs, re-plans when an inspector is missing, and refuses to close without proof.

**[CLICK NEXT]**

## Slide 7: Novelty 1, information gain (Bipra, 0:28)

> Novelty one: **investigate where information is cheapest**. We start at 50, 35 and 15 percent: 1.44 bits of uncertainty. For each action, the agent computes the bits it will remove. The ground survey removes most, **0.91 bits**, but costs **₹60,000**. The records request gives **0.50 bits** for **₹2,000**, so it ranks first. A new satellite pass gives zero bits about *which* source.

**[CLICK NEXT]**

## Slide 8: Novelty 2, a claim is not evidence (Bipra, 0:24)

> Novelty two: **a claim is not evidence**. A case closes only when an **independent** measurement is clearly lower: the top of the new range must be below the bottom of the old one. Here **760 is below 1,302**, so it is verified. A claim alone is rejected. If measurements disagree, we measure again.

**[CLICK NEXT]**

## Slide 9: Architecture (Mandar, 0:20)

> Under the hood: the agent calls six tools. All maths and decisions run in a deterministic, tested core. An LLM only drafts text, and it is optional: without a key, we use templates. Everything is logged and shown on a React dashboard, in one Docker container.

**[CLICK NEXT]**

## Slide 10: Live demo (Mandar, 2:45)

> Let me show you the live system.

**[SWITCH TO BROWSER]** *(The site is already open on the landing page, zoomed so it fills the screen. Reset demo was clicked before the session.)*

| Clock | Click | Say (Mandar) |
|---|---|---|
| 0:00 | Landing page | "This is PlumeProof, live. Top right: Reset demo and the LLM badge. Both modes work." |
| 0:10 | **Start live demo** | "This replays the Kanjur case in 11 steps. Teal tags are real data. Dashed tags are simulated." |
| 0:20 | **Next** (step 1) | "Real plumes from 9 February 2025. The agent opens a case and finds who is responsible from the facility zones." |
| 0:32 | **Next** (step 2) | "Three hypotheses: waste 50, gas 35, flare 15 percent." |
| 0:42 | **Next** (step 3) | "The planner. The records request gives the most information per rupee. The agent asks for approval." |
| 0:55 | **Approve** (step 4) | "I approve. That click is the human decision." |
| 1:02 | **Next** (step 5) | "Simulated: the gas-imaging inspector is not available. The agent removes that option and re-ranks. It does not get stuck." |
| 1:17 | **Next** (step 6) | "The records show a gas-system fault. Bayes' rule: gas collection goes to 65 percent, waste drops to 6." |
| 1:30 | **Approve** (step 7) → **Approve** (step 8) | "I approve the source, then the notice to the operator." |
| 1:42 | *(Stop on the red banner, step 8)* | "Now the operator says: fixed, please close. **The agent says no.** There is no independent measurement. A claim is not evidence. A checklist would close the case here." |
| 2:00 | **Next** (step 9) | "An independent measurement arrives: 610 plus or minus 150. The top, 760, is below 1,302, so the reduction is verified." |
| 2:15 | **Approve** (step 10) | "A human approves the closure." |
| 2:20 | **Next** (step 11) | "April 2026, real data: about 3,300 kilograms per hour again. The agent **reopens the case** automatically. That is why this needs to be an agent." |
| 2:35 | **Evaluation** tab | "And this table comes from running 25 simulated cases. Bipra will explain it." |

**[BACK TO SLIDES]** *(Go to slide 11.)*

## Slide 11: Results (Bipra, 0:30)

> We tested three policies on the same 25 simulated cases. Alert-only and the checklist close on the operator's claim, so **25 of 25** of their closures are false. PlumeProof: **zero**. It found the right source every time, using **0.72** inspections per case against **1.80** for the checklist. The accountable party is known in **1 day**, not 7 or 30. Honestly, the zero comes from the closure rule by design; the table shows that the planner keeps that rule affordable.

**[CLICK NEXT]**

## Slide 12: Impact, limits, thank you (Bipra, 0:15)

> Our values are illustrative and operations are simulated. Next: calibrate with engineers and pilot with a regulator. Every methane plume deserves an investigation. Every claimed fix deserves evidence. Thank you.

---

## Fallback plan (30 seconds, Mandar)

| Problem | Do this (under 30 s) | Say |
|---|---|---|
| Render is slow or asleep | Switch to the second tab, already open at `http://localhost:8000` (start it before the session: `colima start`, then `docker start pp`). | "We'll use the local copy. It's the same build." |
| Both are down | The site falls back to its built-in offline snapshot (an amber "Offline snapshot mode" banner). Click through the replay as normal. | "This is a recorded snapshot of the same run." |
| Laptop or browser problem | **[BACK TO SLIDES]**, go back to slide 2 and play the 60-second video, then show slide 10's three screenshots. | "Here is the same flow on video." |
| Approve button doesn't respond | Press **Next**. If still stuck, click **Reset demo** and **Start live demo**, then skip to step 8 with **Next** and **Approve**. | "Let me jump to the key moment." |

Bipra keeps time. If the demo passes **3:00**, Bipra says "Thank you, Mandar" and moves to slide 11.

---

## Q&A: 12 likely questions (20–40 s each)

**1. Why is this agentic and not just a checklist? (Bipra)**
A checklist runs the same steps in the same order and closes when the operator says "fixed". Our agent keeps the case open for months, updates its beliefs after every result, picks the next action by information per rupee, re-plans when an inspector is not available, refuses closure without evidence, and reopens on a new plume. In our test, the checklist used 1.80 inspections per case to find the source; we used 0.72.

**2. Where do the likelihoods come from? (Bipra)**
They are illustrative values, written in our assumptions file. We chose them so the engine reproduces the worked example in our proposal. When we change every likelihood by up to 20 percent, the top action stays the same in 100 percent of 200 draws. In a real deployment, environmental engineers would calibrate them, and every closed case adds labelled data.

**3. What if the LLM hallucinates? (Bipra)**
The LLM cannot change anything. All maths, rankings, verdicts and state changes are deterministic Python with 128 tests. The LLM only drafts the text of notices, and a human approves every notice. With no API key, the app runs on templates. You can see the "LLM off" badge.

**4. How does this scale to 5,000 alerts? (Mandar)**
Each case is a small, independent state machine, and the maths takes microseconds. The hard limit is human time, and that is exactly what the planner saves: cheap, informative checks first. The approval queue and deadline tracking let a small team supervise many cases. For production, we would move to Postgres with PostGIS and a task queue.

**5. Why not verify with satellite data alone? (Bipra)**
UNEP itself says satellite data alone cannot confirm mitigation. A missing plume could be clouds, wind or the detection limit, and revisits are weeks apart. So closure needs an independent measurement with an uncertainty range. But we still use new satellite passes to **reopen** cases: that is what happened at Kanjur in April 2026.

**6. Isn't "zero false closures" true by construction? (Bipra)**
Partly, yes, and that is the point. The closure rule is something a claim cannot pass. The evaluation shows what it costs, one extra measurement campaign per case, and that the planner still needs fewer inspections to find the source: 0.72 against 1.80. Cost per resolved case is ₹128,000 against ₹136,667 for the checklist.

**7. What is real and what is simulated? (Mandar)**
The Carbon Mapper plumes at Kanjur are real: 9 February 2025 and 3 April 2026. The operator replies, inspector availability, records, the repair claim and the follow-up measurement are simulated. Every screen labels each item as real data, agent action, simulated event or human decision.

**8. What if two measurements disagree? (Bipra)**
We keep both and the verdict is **inconclusive**. The agent asks for another measurement. It never picks the convenient one.

**9. What if the operator never replies? (Mandar)**
The `track_deadline` tool flags the overdue task. The agent escalates, treats that action as giving no information, and re-ranks the remaining options. You saw the same re-planning when the gas-imaging inspector was unavailable.

**10. What does λ do? (Bipra)**
λ turns days into rupees: it is the cost of delay, ₹1,000 per day in our demo. A high λ favours fast actions. With λ at zero, the ranking is by money alone. The records request ranks first in both cases. The planner page has a slider to show this live.

**11. Who would actually use this, and is there a privacy issue? (Mandar)**
Users are regulators such as a state pollution control board, the city authority that owns the site, the operator, and UN focal points. The data is facility-level emissions, not personal data. Notices go only to the bodies responsible for the facility, and a human sends them. Every decision is logged with its evidence.

**12. Why does reopening reset the beliefs to 50, 35, 15? (Bipra)**
The 2025 repair was verified, so the gas-system finding explained the 2025 plume. A plume 14 months later could be a failed repair or a new source. Treating the old answer as current would be over-confident. So the agent restarts from the map-based prior and keeps the full history in the audit log.

*Live answers during Q&A (Mandar):*
- **Case page → Try to close case** shows the state machine rejecting closure, with its reason.
- **Planner → λ slider / Mark unavailable** shows the ranking recompute live.
- **What-if** shows Bayes' rule updating for any action and outcome.
