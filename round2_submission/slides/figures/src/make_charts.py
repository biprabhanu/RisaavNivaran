"""Charts for the Round 2 slides/report, generated ONLY from numbers computed by the real code
(numbers.json from compute_numbers.py, evaluation_numbers.json from scenarios.run_evaluation; both match
docs/EVALUATION.md). Run: uv run --with matplotlib python make_charts.py"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.dirname(HERE)
TEAL, TEAL_L, SLATE, SLATE_L, SLATE_D, RED, GREEN = "#0d9488", "#5eead4", "#64748b", "#cbd5e1", "#0f172a", "#dc2626", "#16a34a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": SLATE_L, "axes.labelcolor": SLATE_D, "xtick.color": SLATE_D, "ytick.color": SLATE,
                     "axes.titleweight": "bold", "axes.titlesize": 15, "savefig.dpi": 200, "savefig.bbox": "tight"})
N = json.load(open(os.path.join(HERE, "numbers.json")))
E = json.load(open(os.path.join(HERE, "evaluation_numbers.json")))
pol = {p["policy_id"]: p for p in E["policies"]}
ORDER = ["A", "B", "C", "C_noplan"]
NAMES = {"A": "A: Alert-only", "B": "B: Fixed\nchecklist", "C": "C: PlumeProof", "C_noplan": "C-ablation\n(planner off)"}

def bars(ax, vals, colors, fmt):
    b = ax.bar([NAMES[k] for k in ORDER], vals, color=colors, width=0.62)
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, r.get_height(), fmt(v), ha="center", va="bottom", fontsize=14, fontweight="bold", color=SLATE_D)
    ax.yaxis.grid(True, color="#e2e8f0"); ax.set_axisbelow(True)

# 1. False closures (headline)
fig, ax = plt.subplots(figsize=(7.5, 4.2))
v = [pol[k]["false_closures"] for k in ORDER]
bars(ax, v, [RED if x > 0 else TEAL for x in v], lambda x: f"{x}/25")
ax.set_ylim(0, 29); ax.set_ylabel("False closures (of 25 cases)")
ax.set_title("Cases closed without independent evidence")
fig.savefig(os.path.join(OUT, "chart_false_closures.png")); plt.close(fig)

# 2. Source-identification inspections per case
fig, ax = plt.subplots(figsize=(7.5, 4.2))
v = [pol[k]["attribution_inspections_per_case"] for k in ORDER]
bars(ax, v, [SLATE_L, SLATE, TEAL, TEAL_L], lambda x: f"{x:.2f}")
ax.set_ylim(0, 2.2); ax.set_ylabel("Field inspections per case")
ax.set_title("Inspections used to identify the source")
fig.savefig(os.path.join(OUT, "chart_source_inspections.png")); plt.close(fig)

# 3. Days to accountable stakeholder + traceability
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.0))
v = [pol[k]["mean_days_to_stakeholder"] for k in ORDER]
bars(a1, v, [SLATE_L, SLATE, TEAL, TEAL_L], lambda x: f"{x:.0f} d"); a1.set_title("Days to accountable stakeholder"); a1.set_ylim(0, 35)
v = [pol[k]["traceability_pct"] for k in ORDER]
bars(a2, v, [SLATE_L, SLATE, TEAL, TEAL_L], lambda x: f"{x:.0f}%"); a2.set_title("Decision traceability"); a2.set_ylim(0, 115)
for a in (a1, a2): a.tick_params(axis="x", labelsize=11)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "chart_stakeholder_traceability.png")); plt.close(fig)

# 4. Ablation: days to closure
fig, ax = plt.subplots(figsize=(6.5, 3.6))
ks = ["C", "C_noplan"]; v = [pol[k]["mean_days_to_closure"] for k in ks]
b = ax.barh([NAMES[k].replace("\n", " ") for k in ks], v, color=[TEAL, TEAL_L], height=0.55)
for r, x in zip(b, v): ax.text(x + 1, r.get_y() + r.get_height() / 2, f"{x:.1f} days", va="center", fontsize=13, fontweight="bold")
ax.set_xlim(0, 95); ax.set_xlabel("Mean days to closure"); ax.set_title("Planner off: same accuracy, much slower")
ax.invert_yaxis(); fig.savefig(os.path.join(OUT, "chart_ablation.png")); plt.close(fig)

# 5. Verification interval chart (Kanjur)
V = N["verification"]
fig, ax = plt.subplots(figsize=(8, 3.2))
pre_c, post_c = (V["pre_low"] + V["pre_high"]) / 2, (V["post_low"] + V["post_high"]) / 2
ax.errorbar([pre_c], [1], xerr=[[pre_c - V["pre_low"]], [V["pre_high"] - pre_c]], fmt="o", color=SLATE, capsize=8, lw=4, ms=10)
ax.errorbar([post_c], [0], xerr=[[post_c - V["post_low"]], [V["post_high"] - post_c]], fmt="o", color=GREEN, capsize=8, lw=4, ms=10)
ax.axvline(V["pre_low"], color=RED, ls="--", lw=1.5)
ax.text(V["pre_low"] + 25, 0.5, f"pre − u = {V['pre_low']:,.0f}", color=RED, fontsize=12, va="center")
ax.text(V["post_high"] + 25, 0.12, f"post + u = {V['post_high']:,.0f}", color=GREEN, fontsize=12)
ax.set_yticks([0, 1]); ax.set_yticklabels([f"Post (May 2025)\n{post_c:,.0f} ± {post_c - V['post_low']:,.0f}", f"Pre (Feb 2025)\n{pre_c:,.0f} ± {pre_c - V['pre_low']:,.0f}"])
ax.set_xlim(0, 2500); ax.set_ylim(-0.6, 1.6); ax.set_xlabel("Methane emission rate (kg/h)")
ax.set_title(f"{V['post_high']:,.0f} < {V['pre_low']:,.0f}  →  VERIFIED REDUCTION")
fig.savefig(os.path.join(OUT, "chart_verification.png")); plt.close(fig)

# 6. Bayes update (prior vs fault posterior)
H = [("waste_surface", "Waste surface"), ("gas_collection", "Gas collection"), ("flare", "Flare")]
fig, ax = plt.subplots(figsize=(7.5, 3.8))
x = range(len(H)); w = 0.38
pr = [N["prior"][h] * 100 for h, _ in H]; po = [N["fault_found"]["posterior"][h] * 100 for h, _ in H]
b1 = ax.bar([i - w / 2 for i in x], pr, w, color=SLATE_L, label=f"Prior (H = {N['entropy']:.2f} bits)")
b2 = ax.bar([i + w / 2 for i in x], po, w, color=TEAL, label=f"After 'fault found' (H = {N['fault_found']['entropy_after']:.2f} bits)")
for r, val in list(zip(b1, pr)) + list(zip(b2, po)):
    ax.text(r.get_x() + r.get_width() / 2, val + 1, f"{val:.0f}%", ha="center", fontsize=13, fontweight="bold")
ax.set_xticks(list(x)); ax.set_xticklabels([l for _, l in H]); ax.set_ylim(0, 80); ax.set_ylabel("P(source)")
ax.legend(frameon=False, fontsize=11, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2); ax.set_title("Bayes' rule after the records request")
fig.savefig(os.path.join(OUT, "chart_bayes.png")); plt.close(fig)

# 7. Kanjur real observations
fig, ax = plt.subplots(figsize=(7, 3.6))
lab = ["9 Feb 2025\nPlume A", "9 Feb 2025\nPlume B", "3 Apr 2026\nTwo plumes, combined"]; val = [1600, 136, 3300]
b = ax.bar(lab, val, color=[TEAL, TEAL, TEAL], width=0.55)
for r, v_ in zip(b, val): ax.text(r.get_x() + r.get_width() / 2, v_ + 50, f"~{v_:,} kg/h", ha="center", fontsize=13, fontweight="bold")
ax.set_ylim(0, 3800); ax.set_ylabel("kg CH$_4$ / hour"); ax.set_title("Carbon Mapper observations, Kanjur (real data)")
fig.savefig(os.path.join(OUT, "chart_kanjur.png")); plt.close(fig)
print("charts written to", OUT)
