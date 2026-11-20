"""Numbers-consistency check for the Round 2 package.
Every number token in the slides (PDF text), speech, report and INFO must be in the allowed set, which is built from the
engine outputs (numbers.json, evaluation_numbers.json) plus the facts quoted from RisaavNivaran.pdf / docs/ASSUMPTIONS.md.
Run: python3 check_consistency.py   (exit 1 on unknown numbers)"""
import json, os, re, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.abspath(os.path.join(H, "../../.."))
N = json.load(open(os.path.join(H, "numbers.json"))); E = json.load(open(os.path.join(H, "evaluation_numbers.json")))
allowed = set()
def add(*xs):
    for x in xs: allowed.add(str(x))
def num(x, d): add(f"{x:.{d}f}", f"{x:,.{d}f}")
# Engine numbers
num(N["entropy"], 2); num(N["fault_found"]["entropy_after"], 2); num(N["fault_found"]["p"], 2); num(N["lambda"], 0)
for h, v in N["prior"].items(): num(v * 100, 0)
for h, v in N["fault_found"]["posterior"].items(): num(v * 100, 0)
num(N["no_fault"]["posterior"]["waste_surface"] * 100, 0); num(N["no_fault"]["p"] * 100, 0)
for a in N["actions"]:
    num(a["eig"], 2); num(a["cost"], 0); num(a["time"], 0); add(a["rank"])
    if a["gain_per_10k"]: num(a["gain_per_10k"], 2)
    if a["cost"]: add(f"{a['cost']/1000:.0f}")
for k, v in N["verification"].items():
    if isinstance(v, (int, float)): num(v, 0)
add("1,736", "1736", "434", "610", "150")  # kanjur.PRE_MEASUREMENT and replay follow-up (docs/ASSUMPTIONS.md)
for p in E["policies"]:
    add(p["false_closures"], p["n_cases"], p["resolved_cases"]); num(p["correct_attribution_rate"] * 100, 0)
    num(p["attribution_inspections_per_case"], 2); num(p["inspections_per_resolved"], 2); num(p["cost_per_resolved_inr"], 0)
    num(p["mean_days_to_stakeholder"], 0); num(p["mean_days_to_stakeholder"], 1); num(p["traceability_pct"], 1); num(p["traceability_pct"], 0)
    num(p["mean_days_to_closure"], 1)
s = E["sensitivity"]; num(s["top_action_stability_pct"], 0); num(s["mean_kendall_tau"], 3); add(s["n_draws"], s["c_false_closures_perturbed"])
num(s["c_inspections_per_resolved_perturbed"], 2); add(E["seed"], E["n"])
# Proposal PDF facts / docs
add("5,000", "33", "13", "80", "2030", "30", "1,015", "6", "40", "10", "22", "11", "50", "3", "1,600", "136", "3,300", "2025", "2026", "9", "20",
    "21", "22", "23", "2022", "5", "7", "4", "8,000", "95", "1,500", "19.13", "72.93", "100", "0.8", "14", "25", "60", "12", "2511.21777", "25592",
    "1.2", "0.8", "2", "1", "0", "8", "11", "128", "3.12", "18", "8000", "9692886318", "91", "24", "4511", "4.5", "290", "1920", "1080", "1366", "768",
    "16", "9", "69", "2,000", "25,000", "60,000", "10,000", "10k", "15", "35", "65", "29", "84", "45", "0.5", "1.0", "17", "3.0")
add(*range(1, 21), "130", "140", "520", "230", "02", "72")  # slide page numbers, speaking rate (wpm), case id KJ-2025-02, image width %
# timing / clock values in the speech are mm:ss and excluded below
files = {"slides": subprocess.run(["pdftotext", os.path.join(R, "slides/plumeproof_round2.pdf"), "-"], capture_output=True, text=True).stdout,
         "speech": open(os.path.join(R, "speech/speech_8min.md")).read(), "report": open(os.path.join(R, "report/round2_report.md")).read(),
         "info": open(os.path.join(R, "INFO.md")).read()}
bad = 0
for name, txt in files.items():
    txt = re.sub(r"\d+:\d\d", " ", txt)                       # clock times
    txt = re.sub(r"https?://\S+|github\.com/\S+|\S+@\S+|`[^`]*`", " ", txt)   # urls, emails, code
    toks = re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", txt)
    unknown = sorted({t.rstrip(",.") for t in toks if t.rstrip(",.") not in allowed})
    print(f"{name:7s}: {len(toks)} number tokens, unknown: {unknown or 'none'}"); bad += len(unknown)
# Cross-check: headline numbers must appear in all four files
heads = ["0.50", "0.91", "65", "760", "1,302", "25/25", "0/25", "0.72", "1.80", "1.44"]
for hd in heads:
    alt = {"25/25": "25 of 25", "0/25": "zero"}.get(hd, hd)
    missing = [n for n, t in files.items() if hd not in t and alt not in t]
    if missing and not (hd in ("1.44",) and missing == ["info"]): print(f"headline {hd} missing from {missing}")
sys.exit(1 if bad else 0)
