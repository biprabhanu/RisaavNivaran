# PlumeProof: final-round info sheet

**PlumeProof: From Satellite Methane Alerts to Verified Mitigation**
Agentic AI Hackathon 2026 · Ulster University

| | |
|---|---|
| Team Number | **[fill in]** |
| Team Name | RisaavNivaran |
| Problem Theme | Agentic AI for Climate, Sustainability & Green Innovation |
| Institute | Indian Institute of Technology Bombay, India |
| Team Members | Bipra Bhanu Mohanty (Team Lead), Mandar Deshmukh |
| Contact | 24b4511@iitb.ac.in · +91 9692886318 |

## Links

| What | Where |
|---|---|
| **Live demo** | **https://plumeproof.onrender.com** |
| **GitHub** | **https://github.com/biprabhanu/RisaavNivaran** |
| Local fallback | `colima start` → `docker start pp` → open **http://localhost:8000** |
| Offline fallback | If the backend can't be reached, the site replays a bundled snapshot (amber "Offline snapshot mode" banner) |
| Video | **`[fill in: path to plumeproof_60s.mp4]`** (script: `docs/DEMO_SCRIPT.md` §B) |

## Format: 10 minutes = 6 presentation + demo, then 4 Q&A

The demo carries the most marks, so it gets the biggest block. The video plays first, as recommended.

| Slide | Content | Speaker | Time | Clock |
|---|---|---|---|---|
| 1 | Front page | Bipra | 0:10 | 0:10 |
| 2 | 60-second video | Bipra | 0:45 | 0:55 |
| 3 | Problem + Kanjur test case (real data) | Bipra | 0:30 | 1:25 |
| 4 | Solution: input → agent → human approval → verified outcome; end users | Mandar | 0:30 | 1:55 |
| 5 | USPs: EIG planning, evidence-gated closure, auto-reopen | Bipra | 0:40 | 2:35 |
| 6 | How it works: deterministic core, LLM only drafts | Bipra | 0:15 | 2:50 |
| 7 | **Live demo** | Mandar | **2:30** | 5:20 |
| 8 | Results | Bipra | 0:25 | 5:45 |
| 9 | Impact, limits, next steps, thank you | Bipra | 0:15 | **6:00** |
| 10 | Backup: assumptions, real vs simulated (Q&A only) | — | — | — |

If the demo runs long, jump from step 8 straight to step 11 (reopened) and go back to slide 8.

## Pre-demo checklist

- [ ] **2 minutes before:** open https://plumeproof.onrender.com to wake the free instance. The first load can take about a minute.
- [ ] Click **Reset demo** (top right) and wait for the "Demo reset" toast.
- [ ] Set the browser zoom so the page fills the projector: 1920×1080 → 100%, 1366×768 → 80%. Go full screen.
- [ ] Second tab: **http://localhost:8000**, already running (`colima start`, `docker start pp`) and reset.
- [ ] Video file open in a player, paused at 0:00, volume checked.
- [ ] Slides open full screen (`slides/plumeproof_round2.pdf`) on slide 1.
- [ ] Notifications off, charger plugged in, Wi-Fi or hotspot tested.

## Demo click path (2:30, Replay page)

1. Landing page → **Start live demo** (opens on step 0, no autoplay). Point out the labels: teal = real data, dashed = simulated.
2. **Next** ×2: real plumes (1,600 and 136 kg/h) → three hypotheses 50 / 35 / 15%, 1.44 bits.
3. **Next**: planner. Records request ranks first (0.50 bits for ₹2,000).
4. **Approve**: the human approves; the agent never acts alone.
5. **Next**: OGI inspector unavailable → excluded before ranking, re-planned.
6. **Next**: records show a fault → gas collection 65%. **Approve** the attribution.
7. **Approve** → **CASE CLOSURE REJECTED** (red banner). Pause two seconds: a claim is not evidence.
8. **Next**: 610 ± 150 kg/h → VERIFIED (760 < 1,302). **Approve** the closure.
9. **Next**: real plume, 3 Apr 2026 (about 3,300 kg/h) → **CASE REOPENED**. Back to slides.

For Q&A: **Case → Try to close case** (guardrail), **Planner → λ slider / Mark unavailable**, **What-if**, **Reject** on any approval card.

## Key numbers (computed by the code or quoted from the proposal PDF)

| Topic | Number |
|---|---|
| Problem | 5,000+ UN MARS alerts · 13% response · UN target 80% by 2030 |
| Kanjur (real) | 9 Feb 2025: about 1,600 and 136 kg/h · 3 Apr 2026: about 3,300 kg/h combined |
| Prior | waste 50% · gas 35% · flare 15% · H = 1.44 bits |
| EIG | records 0.50 bits / ₹2,000 · OGI 0.41 / ₹25,000 · ground 0.91 / ₹60,000 · satellite 0.00 / ₹0 |
| Bits per ₹10k | records 2.50 · OGI 0.17 · ground 0.15 (λ = ₹1,000/day) |
| Bayes (fault found, P = 0.43) | gas 65% · flare 29% · waste 6% · H = 1.16 bits |
| Verification | pre 1,736 ± 434 · post 610 ± 150 · 760 < 1,302 → VERIFIED · recurrence threshold 760 kg/h |
| Evaluation (25 scenarios, seed 2026) | false closures A 25/25 · B 25/25 · **C 0/25** |
| | source-ID inspections per case B 1.80 vs **C 0.72** · cost per resolved case B ₹136,667 vs C ₹128,000 |
| | days to stakeholder 30 / 7 / **1** · traceability 0% / 82.8% / **100%** · correct source 0% / 84% / **100%** |
| Ablation (planner off) | 0/25 false closures, but 78.8 vs 46.7 days to closure |
| Sensitivity (±20%, 200 draws) | top action stable 100% · Kendall τ 0.955 · 0 false closures on perturbed worlds |
| Engineering | 128 backend tests · 3 browser e2e tests · one Docker container · LLM optional |

## Files

| Path | What |
|---|---|
| `slides/plumeproof_round2.tex` / `.pdf` | Minimal light-theme Beamer deck, 16:9, 10 pages or fewer (9 main + 1 backup) |
| `slides/figures/*.png` | 1920×1080 app screenshots, banner crops and charts |
| `slides/figures/numbers.tex` | Generated LaTeX number macros (do not edit) |
| `slides/figures/src/` | Scripts that compute the numbers, draw the charts, take the screenshots and check that the numbers match across files |
| `report/round2_report.md` / `.pdf` | Detailed written report in plain language |
| `speech/speech_6min.md` | **Local only, not in git.** Word-for-word 6-minute script for Bipra and Mandar, timing, cues, fallback plan, 12 Q&A answers |
| `INFO.md` | This sheet |

**Rebuild:**
```bash
cd backend && source .venv/bin/activate && python ../round2_submission/slides/figures/src/compute_numbers.py && cd ..
cd round2_submission/slides/figures/src && python3 gen_macros.py && uv run --with matplotlib python make_charts.py && cd ../..
tectonic plumeproof_round2.tex
cd ../report && pandoc round2_report.md -o round2_report.pdf --pdf-engine=tectonic
```

## Still to fill in by hand

1. **Team Number**: on the front slide (`[TEAM NO.]`) and in the table at the top of this sheet.
2. **Video path**: the `plumeproof_60s.mp4` location in the Links table above.
