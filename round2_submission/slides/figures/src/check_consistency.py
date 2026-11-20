"""Numbers-consistency check for the Round 2 package.
Every number token in the slides (PDF text), report, INFO and (if present locally) speech/*.md must be in the allowed set, which is built from the
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
# Worked-example arithmetic shown step by step in the report: recomputed here from the engine (never typed).
try:
    sys.path.insert(0, os.path.join(R, "..", "backend"))
    from plumeproof import config as _cfg
    from plumeproof.bayes import entropy as _H, normalise as _norm
    from plumeproof.bayes import expected_information_gain as _eig
    from plumeproof.planner import score as _score
except Exception as _e:  # engine not importable (e.g. no venv): derived values stay unknown and are reported
    _cfg = None
if _cfg is not None:
    _prior = dict(_cfg.DEFAULT_PRIOR)
    _acts = {a.id: a for a in _cfg.ACTIONS}
    if _prior and "records_request" in _acts:
        _o = _acts["records_request"].outcomes[0]
        _L = dict(_o.likelihood)
        _j = {h: _prior[h] * _L[h] for h in _prior}
        _pf = sum(_j.values())
        for v in _j.values(): num(v, 3)
        for v in _L.values(): num(v, 2); num(v, 3); num(100 * v, 1); num(100 * v, 0)
        for v in _prior.values(): num(v, 2)
        num(1 - _pf, 2)
        num(_H(_norm(_j)), 2); num(_H(_norm({h: _prior[h] * (1 - _L[h]) for h in _prior})), 2)
    for a in _acts.values():
        num(a.cost_inr + _cfg.DEFAULT_LAMBDA * a.time_days, 0)   # cost + λ·time at the default λ
        try:
            num(_score(_eig(_prior, a), a.cost_inr, a.time_days, _cfg.DEFAULT_LAMBDA) * 10_000, 2)  # score per ₹10k
        except Exception:
            pass
import glob, sys
def _read(path):
    return open(path).read() if os.path.exists(path) else None
files = {"slides": subprocess.run(["pdftotext", os.path.join(R, "slides/plumeproof_round2.pdf"), "-"], capture_output=True, text=True).stdout,
         "report": _read(os.path.join(R, "report/round2_report.md")), "info": _read(os.path.join(R, "INFO.md"))}
# The presenter speech is local-only (gitignored): check every speech/*.md that exists, skip quietly if none.
for sp in sorted(glob.glob(os.path.join(R, "speech", "*.md"))):
    files["speech:" + os.path.basename(sp)] = open(sp).read()
if not any(k.startswith("speech") for k in files):
    print("speech : not present (local-only file), skipped")
files = {k: v for k, v in files.items() if v is not None}
bad = 0
for name, txt in files.items():
    txt = re.sub(r"\d+:\d\d", " ", txt)                       # clock times
    txt = re.sub(r"(?s)^---\n.*?\n---\n", " ", txt)             # pandoc YAML header (font size, margins)
    txt = re.sub(r"\{width=[\d.]+%\}", " ", txt)                  # image widths
    txt = re.sub(r"(?m)^#+\s*[\d.]+\s", "# ", txt)                # section numbers in headings
    txt = re.sub(r"Section \d+(\.\d+)?", " ", txt)                  # cross-references
    if name.startswith("speech"):                                     # word counts / pacing notes, not facts
        txt = re.sub(r"\d+ spoken words|\d+ \+ \d+ clicks|\d+ s of demo", " ", txt)
    txt = re.sub(r"(?m)^\|[^\n]*\|\s*\d+\s*\|\s*$", " ", txt) if name.startswith("speech") else txt  # word-count column
    txt = re.sub(r"https?://\S+|github\.com/\S+|\S+@\S+|`[^`]*`", " ", txt)   # urls, emails, code
    toks = re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", txt)
    unknown = sorted({t.rstrip(",.") for t in toks if t.rstrip(",.") not in allowed})
    print(f"{name:7s}: {len(toks)} number tokens, unknown: {unknown or 'none'}"); bad += len(unknown)
# Cross-check: headline numbers must appear in every file that was checked
heads = ["0.50", "0.91", "65", "760", "1,302", "25/25", "0/25", "0.72", "1.80", "1.44"]
for hd in heads:
    alt = {"25/25": "25 of 25", "0/25": "zero"}.get(hd, hd)
    missing = [n for n, t in files.items() if hd not in t and alt not in t]
    missing = [m for m in missing if not (hd == "1.44" and m == "info")]   # INFO's key-number table omits the entropy
    if missing: print(f"headline {hd} missing from {missing}")
sys.exit(1 if bad else 0)
