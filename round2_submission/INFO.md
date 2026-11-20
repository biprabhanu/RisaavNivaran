# PlumeProof: Round 2 info sheet

**Team RisaavNivaran, IIT Bombay** · Agentic AI Hackathon 2026 · Ulster University · 21–22 November 2026

## Links

| What | Where |
|---|---|
| Live demo (Render) | **`[FILL IN: https://<service>.onrender.com]`** |
| Local fallback | `colima start` → `docker start pp` → open **http://localhost:8000** |
| Offline fallback | If the backend is unreachable, the site replays a bundled snapshot (amber "Offline snapshot mode" banner) |
| GitHub | https://github.com/biprabhanu/RisaavNivaran |
| Video | **`[FILL IN: path to plumeproof_60s.mp4]`** (script: `docs/DEMO_SCRIPT.md` §B) |

## Pre-demo checklist

- [ ] **2 minutes before:** open the Render URL to wake the free instance. The first load can take about 50 s.
- [ ] Click **Reset demo** (top right) and wait for the toast "Demo reset…".
- [ ] Check that the **LLM badge** shows "LLM: on" or "LLM: off (template mode)". Both work.
- [ ] Set browser zoom so the page fills the projector: 1920×1080 → 100%; 1366×768 → 80%. Use full screen (F11 / ⌃⌘F).
- [ ] Second tab: **http://localhost:8000**, already running (`colima start`, `docker start pp`), and reset too.
- [ ] Video file open in a player and paused at 0:00. Volume checked.
- [ ] Slides open in full-screen PDF mode (`slides/plumeproof_round2.pdf`) on slide 1.
- [ ] Notifications off, laptop charger plugged in, Wi-Fi or hotspot tested.

## Click-path (live demo, about 2:45)

1. **Landing page** → **Start live demo** (the replay opens on step 0 and does not autoplay).
2. **Next**: step 1, real plumes of 9 Feb 2025 (1,600 and 136 kg/h).
3. **Next**: step 2, hypotheses 50 / 35 / 15%, 1.44 bits.
4. **Next**: step 3, planner. The records request ranks first (0.50 bits for ₹2,000).
5. **Approve**: step 4, human approves the records request.
6. **Next**: step 5, OGI inspector unavailable → re-ranked.
7. **Next**: step 6, records show a fault → gas collection 65%. Then **Approve** (step 7: attribution) and **Approve** (step 8: notice).
8. **Stop on the red banner, CASE CLOSURE REJECTED** (step 8). Then **Next**: step 9, 610 ± 150 kg/h → VERIFIED (760 < 1,302).
9. **Approve**: step 10, closed. **Next**: step 11, real plume of 3 Apr 2026 (about 3,300 kg/h) → **CASE REOPENED**. Then open the **Evaluation** tab.

For Q&A: **Case → Try to close case** (guardrail), **Planner → λ slider / Mark unavailable**, **What-if**.

## Key numbers (all computed by the code or quoted from the proposal PDF)

| Topic | Number |
|---|---|
| Problem [1] | 5,000+ MARS alerts in 33 countries · 13% response · UN target 80% by 2030 |
| Kanjur, real [2] | 9 Feb 2025: about 1,600 and 136 kg/h · 3 Apr 2026: about 3,300 kg/h combined |
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
| `slides/plumeproof_round2.tex` / `.pdf` | Beamer deck, 16:9: 12 main slides + 8 backup slides (20 pages) |
| `slides/figures/*.png` | Fresh 1920×1080 app screenshots, `*-crop.png` banner crops and charts |
| `slides/figures/numbers.tex` | Generated LaTeX number macros (do not edit) |
| `slides/figures/src/compute_numbers.py` | Computes the engine numbers from `backend/plumeproof` → `numbers.json` |
| `slides/figures/src/evaluation_numbers.json` | Evaluation results from `scenarios.run_evaluation(2026, 25)` (equal to `docs/EVALUATION.md`) |
| `slides/figures/src/gen_macros.py` | JSON → `numbers.tex` |
| `slides/figures/src/make_charts.py` | JSON → chart PNGs (matplotlib) |
| `slides/figures/src/capture.cjs`, `crop_shots.py` | Playwright screenshots at 1920×1080, and banner crops |
| `slides/figures/src/check_consistency.py` | Checks that every number in the slides, speech and report is allowed |
| `speech/speech_8min.md` | Word-for-word script for two speakers, timing, fallback plan, 12 Q&As |
| `report/round2_report.md` / `.pdf` | 6-page technical report |

**Rebuild:**
```bash
cd backend && source .venv/bin/activate && python ../round2_submission/slides/figures/src/compute_numbers.py && cd ..
cd round2_submission/slides/figures/src && python3 gen_macros.py && uv run --with matplotlib python make_charts.py && cd ../..
tectonic plumeproof_round2.tex
cd ../report && pandoc round2_report.md -o round2_report.pdf --pdf-engine=tectonic
```

## Team

- **Bipra Bhanu Mohanty** (Team Lead): agent architecture, evidence planning, evaluation
- **Mandar Deshmukh**: data pipeline, dashboard, regulatory research
- **Contact:** 24b4511@iitb.ac.in · +91 9692886318
