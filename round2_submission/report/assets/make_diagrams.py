"""Draws the two report-only diagrams (architecture, case lifecycle). Run:
uv run --with matplotlib python make_diagrams.py   (from this folder)"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

TEAL, TEAL_L, SLATE, SLATE_L, INK = "#0d9488", "#ccfbf1", "#64748b", "#f1f5f9", "#0f172a"
RED, RED_L, GREEN_L, AMBER_L = "#dc2626", "#fee2e2", "#dcfce7", "#fef3c7"


def box(ax, x, y, w, h, title, body="", fc=SLATE_L, ec=SLATE, tc=INK, fs=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top", fontsize=fs, fontweight="bold", color=tc)
    if body:
        ax.text(x + w / 2, y + h - 0.62, body, ha="center", va="top", fontsize=fs - 2.2, color="#334155", linespacing=1.35)


def arrow(ax, a, b, color=SLATE, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=14, color=color, lw=1.4, linestyle=ls))


# ---------------- architecture ----------------
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.set_xlim(0, 11); ax.set_ylim(0, 4.6); ax.axis("off")
box(ax, 0.1, 2.5, 2.1, 1.8, "Inputs", "Satellite plume\n(Carbon Mapper)\nfacility zones\nstakeholder registry\nmeasurements")
box(ax, 3.0, 2.2, 3.2, 2.3, "Agent orchestrator", "observe → update beliefs →\nplan → ask approval →\nact → verify → monitor\n\n6 tools: query, overlay, rank,\ndraft, deadline, evaluate", fc=TEAL_L, ec=TEAL)
box(ax, 3.0, 0.15, 3.2, 1.55, "Deterministic core (tested)", "Bayes · EIG planner\nverification rule · state machine", fc="white", ec=TEAL)
box(ax, 7.0, 2.9, 1.9, 1.5, "Human approval", "approve · edit\n· reject", fc=AMBER_L, ec="#d97706")
box(ax, 7.0, 1.0, 1.9, 1.5, "Audit log", "every event,\nlabelled + linked", fc="white", ec=SLATE)
box(ax, 9.3, 2.0, 1.6, 2.3, "Outputs", "ranked plan\nnotices\nverdict\naudit trail\nreopen alert")
box(ax, 0.1, 0.15, 2.1, 1.55, "LLM (optional)", "drafts text only;\ncannot change\nstate", fc="white", ec=SLATE)
arrow(ax, (2.25, 3.4), (2.95, 3.4))
arrow(ax, (4.6, 2.15), (4.6, 1.75), color=TEAL, style="<|-|>")
arrow(ax, (6.25, 3.65), (6.95, 3.65)); arrow(ax, (6.95, 3.2), (6.25, 3.2))
arrow(ax, (6.25, 2.5), (6.95, 1.8))
arrow(ax, (8.95, 3.4), (9.25, 3.2))
arrow(ax, (2.25, 0.95), (2.95, 2.4), ls="--")
ax.text(2.35, 1.75, "drafts", fontsize=8.5, color=SLATE, rotation=62)
fig.savefig("architecture.png", dpi=200, bbox_inches="tight", facecolor="white")

# ---------------- lifecycle ----------------
fig, ax = plt.subplots(figsize=(11, 3.6))
ax.set_xlim(0, 11); ax.set_ylim(-0.45, 3.1); ax.axis("off")
steps = [("Open", SLATE_L, SLATE), ("Source attribution\npending", AMBER_L, "#d97706"), ("Investigation\nrequested", AMBER_L, "#d97706"),
         ("Repair\nreported", AMBER_L, "#d97706"), ("Verification\npending", AMBER_L, "#d97706")]
for i, (t, fc, ec) in enumerate(steps):
    x = 0.05 + i * 2.2
    ax.add_patch(FancyBboxPatch((x, 2.0), 1.9, 0.95, boxstyle="round,pad=0.02,rounding_size=0.1", fc=fc, ec=ec, lw=1.3))
    ax.text(x + 0.95, 2.475, t, ha="center", va="center", fontsize=9, fontweight="bold", color=INK)
    if i < len(steps) - 1:
        arrow(ax, (x + 1.93, 2.475), (x + 2.17, 2.475))
outs = [("Verified reduction", GREEN_L, "#16a34a"), ("Inconclusive", SLATE_L, SLATE), ("Still leaking", RED_L, RED)]
for j, (t, fc, ec) in enumerate(outs):
    x = 4.2 + j * 2.25
    ax.add_patch(FancyBboxPatch((x, 0.3), 2.0, 0.75, boxstyle="round,pad=0.02,rounding_size=0.1", fc=fc, ec=ec, lw=1.3))
    ax.text(x + 1.0, 0.675, t, ha="center", va="center", fontsize=9.5, fontweight="bold", color=INK)
    arrow(ax, (9.8, 1.97), (x + 1.0, 1.1))
ax.add_patch(FancyBboxPatch((0.6, 0.3), 2.6, 0.75, boxstyle="round,pad=0.02,rounding_size=0.1", fc=RED_L, ec=RED, lw=1.3))
ax.text(1.9, 0.675, "Recurring (reopened)", ha="center", va="center", fontsize=9.5, fontweight="bold", color=INK)
arrow(ax, (4.15, 0.675), (3.25, 0.675), color=RED)
ax.text(3.7, 0.85, "new plume", ha="center", fontsize=8.5, color=RED)
ax.text(5.5, -0.3, "There is no arrow from 'Repair reported' to 'Verified reduction': a claim alone can never close a case.",
        ha="center", fontsize=9.5, color=RED, style="italic")
fig.savefig("lifecycle.png", dpi=200, bbox_inches="tight", facecolor="white")
print("ok")
