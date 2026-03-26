"""
HalfFull — EDA Presentation Plots  v3  (CI-aligned)
Brand CI:
  Background   #ECEEF8  soft periwinkle-lavender
  Card         #FFFFFF  white on lavender, subtle shadow
  Lime         #D7F068  primary CTA / accent
  Violet       #7765F4  selection, progress, highlights
  Near-black   #0A0A0F  headlines
  Muted        #888899  labels / subtitles
  Title font   Playfair Display (Fraunces stand-in, bold display serif)
  Body font    DM Sans
"""

import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ── Brand tokens ──────────────────────────────────────────────────────────────
BG          = "#ECEEF8"   # lavender page background
CARD        = "#FFFFFF"   # card surface
LIME        = "#D7F068"   # primary CTA accent
VIOLET      = "#7765F4"   # selection / progress
NEAR_BLACK  = "#0A0A0F"   # headlines
MUTED       = "#888899"   # labels / subtitles
MUTED_DARK  = "#555566"   # slightly darker muted
CARD_BORDER = "#DDE0F2"   # card spine / grid
DROPPED_BAR = "#B0B3C8"   # dropped-condition bars
DROPPED_LBL = "#AA4455"   # "dropped" italic label

# ── Register brand fonts ──────────────────────────────────────────────────────
_font_dir = os.path.expanduser("~/.local/share/fonts/halffull")
for _f in os.listdir(_font_dir):
    fm.fontManager.addfont(os.path.join(_font_dir, _f))

FONT_TITLE = "Playfair Display"   # bold display serif ≈ Fraunces
FONT_BODY  = "DM Sans"

def _t(size, weight="bold", family=FONT_TITLE):
    return {"fontsize": size, "fontweight": weight, "fontfamily": family,
            "color": NEAR_BLACK}

def _b(size, weight="normal", color=MUTED_DARK):
    return {"fontsize": size, "fontweight": weight, "fontfamily": FONT_BODY,
            "color": color}

# ── Shared axis styling ───────────────────────────────────────────────────────
def style_card_ax(ax, fig=None):
    """White card on lavender background — clean spines, DM Sans ticks."""
    ax.set_facecolor(CARD)
    for spine in ax.spines.values():
        spine.set_edgecolor(CARD_BORDER)
        spine.set_linewidth(0.8)
    ax.tick_params(colors=MUTED_DARK, labelsize=9)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontfamily(FONT_BODY)
        lbl.set_color(MUTED_DARK)

os.makedirs("presentation_assets", exist_ok=True)
np.random.seed(42)


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH 1 — Structural Missingness Heatmap
# ══════════════════════════════════════════════════════════════════════════════

N_PARTICIPANTS = 120
N_DEMO, N_DIET, N_EXAM, N_LAB, N_QUEST = 12, 8, 10, 12, 38

def gen_block_missing(n_rows, n_cols, block_size_frac=0.45):
    data = np.zeros((n_rows, n_cols))
    bs = max(1, int(n_cols * block_size_frac))
    for row in range(n_rows):
        n_blk = np.random.choice([0, 1, 2, 3], p=[0.30, 0.30, 0.25, 0.15])
        for _ in range(n_blk):
            start = np.random.randint(0, n_cols - bs + 1)
            data[row, start:start + bs] = 1
    data[(data == 0) & (np.random.rand(n_rows, n_cols) < 0.05)] = 1
    return data

def gen_random_missing(n_rows, n_cols, rate):
    return (np.random.rand(n_rows, n_cols) < rate).astype(float)

miss = np.hstack([
    gen_random_missing(N_PARTICIPANTS, N_DEMO,  0.10),
    gen_random_missing(N_PARTICIPANTS, N_DIET,  0.15),
    gen_random_missing(N_PARTICIPANTS, N_EXAM,  0.22),
    gen_random_missing(N_PARTICIPANTS, N_LAB,   0.22),
    gen_block_missing( N_PARTICIPANTS, N_QUEST),
])
miss = miss[np.argsort(miss[:, N_DEMO+N_DIET+N_EXAM+N_LAB:].sum(axis=1))[::-1]]

boundaries    = np.cumsum([N_DEMO, N_DIET, N_EXAM, N_LAB, N_QUEST])
domain_labels = ["Demographics\n(~10%)", "Dietary\n(~15%)",
                 "Examination\n(~22%)", "Laboratory\n(~22%)",
                 "Questionnaire\n(~59%)"]
dom_starts    = [0, N_DEMO, N_DEMO+N_DIET, N_DEMO+N_DIET+N_EXAM, N_DEMO+N_DIET+N_EXAM+N_LAB]
dom_centers   = [(dom_starts[i] + boundaries[i]) / 2 for i in range(5)]

cmap = LinearSegmentedColormap.from_list("hf", [CARD, VIOLET], N=2)

fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG)
style_card_ax(ax)

ax.imshow(miss, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")

# Domain separators — lime dashed
for b in boundaries[:-1]:
    ax.axvline(b - 0.5, color=LIME, linewidth=2.2, linestyle="--", alpha=0.9, zorder=4)

# Domain x-labels
ax.set_xticks(dom_centers)
ax.set_xticklabels(domain_labels, fontsize=9.5, fontfamily=FONT_BODY,
                   color=MUTED_DARK, linespacing=1.4)
ax.set_yticks([])
ax.set_ylabel("Participants  (n = 7,437 adults)", fontsize=10,
              fontfamily=FONT_BODY, color=MUTED_DARK, labelpad=8)

# Title
ax.set_title("Structural Missingness: Block Patterns, Not Random Noise",
             pad=16, **_t(14))

# Annotation arrow → rotating modules
ax.annotate(
    "Rotating modules\n(skip logic → block missingness)",
    xy=(N_DEMO+N_DIET+N_EXAM+N_LAB + N_QUEST*0.55, N_PARTICIPANTS*0.28),
    xytext=(N_DEMO+N_DIET+N_EXAM + 2, N_PARTICIPANTS*0.07),
    fontsize=9, fontfamily=FONT_BODY, color=VIOLET, fontweight="bold",
    arrowprops=dict(arrowstyle="->", color=VIOLET, lw=1.8),
)

# Legend
present_p = mpatches.Patch(facecolor=CARD, edgecolor=CARD_BORDER, label="Data present")
missing_p = mpatches.Patch(facecolor=VIOLET, label="Missing value")
leg = ax.legend(handles=[present_p, missing_p], loc="lower right",
                framealpha=0.9, facecolor=CARD, edgecolor=CARD_BORDER,
                fontsize=9, labelcolor=MUTED_DARK)
for t in leg.get_texts():
    t.set_fontfamily(FONT_BODY)

plt.tight_layout(pad=1.6)
plt.savefig("presentation_assets/structural_missingness.png",
            dpi=300, facecolor=BG, bbox_inches="tight")
plt.close()
print("✓  structural_missingness.png")


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH 2 — Class Imbalance  (15 conditions · 4 dropped · 11 production)
# ══════════════════════════════════════════════════════════════════════════════

diseases = {
    "High Blood Pressure": 43.1,
    "High Cholesterol":    39.2,
    "Menopause":           17.1,
    "Diabetes":            15.6,
    "Sleep Disorder":      12.3,
    "Perimenopause Proxy": 10.0,
    "Thyroid Condition":    9.4,
    "Alcohol Use Dis.":     7.8,
    "Anemia":               6.9,
    "Liver Condition":      3.6,
    "Emphysema/Lung":       3.1,
    "Coronary Heart Dis.":  1.9,
    "Kidney Disease":       0.9,
    "Heart Failure":        0.8,
    "Hepatitis B/C":        0.3,
}
DROPPED = {"Hepatitis B/C", "Heart Failure", "Kidney Disease", "Coronary Heart Dis."}

df_prev = (pd.DataFrame(list(diseases.items()), columns=["Disease", "Prevalence (%)"])
             .sort_values("Prevalence (%)").reset_index(drop=True))

fig, ax = plt.subplots(figsize=(13, 7.7), facecolor=BG)
style_card_ax(ax)

# Bars
for _, row in df_prev.iterrows():
    name, val = row["Disease"], row["Prevalence (%)"]
    if name in DROPPED:
        c, h, ec, alpha = DROPPED_BAR, "///", "#9999AA", 0.75
    elif val <= 10.0:
        c, h, ec, alpha = LIME, "", LIME, 1.0
    else:
        c, h, ec, alpha = VIOLET, "", VIOLET, 1.0
    ax.barh(name, val, color=c, hatch=h, height=0.62, zorder=3,
            edgecolor=ec, linewidth=0.7, alpha=alpha)

# Value labels + "dropped" tag
for _, row in df_prev.iterrows():
    name, val = row["Disease"], row["Prevalence (%)"]
    lc = MUTED if name in DROPPED else MUTED_DARK
    ax.text(val + 0.4, name, f"{val:.1f}%",
            va="center", ha="left", fontsize=9,
            fontfamily=FONT_BODY, color=lc)
    if name in DROPPED:
        ax.text(val + 3.8, name, "dropped",
                va="center", ha="left", fontsize=7.5,
                fontfamily=FONT_BODY, color=DROPPED_LBL, fontstyle="italic")

# Threshold line — lime at 3%
ax.axvline(3.0, color=LIME, linestyle="--", linewidth=2.0, alpha=0.85, zorder=2)
ax.text(3.15, 0.28, "< 3% → dropped\n(data sparsity)",
        fontsize=8, fontfamily=FONT_BODY, color=LIME,
        va="bottom", fontstyle="italic")

# Second thin separator at ~10%
ax.axvline(10.2, color=MUTED, linestyle="--", linewidth=1.0, alpha=0.5, zorder=2)

# Grid + limits
ax.grid(axis="x", color=CARD_BORDER, linewidth=0.7, zorder=1)
ax.set_xlim(0, 52)
ax.set_xlabel("Prevalence in NHANES dataset (%)", fontsize=10.5,
              fontfamily=FONT_BODY, color=MUTED_DARK, labelpad=8)

# Y-tick colours
for lbl in ax.get_yticklabels():
    lbl.set_color(MUTED if lbl.get_text() in DROPPED else NEAR_BLACK)
    lbl.set_fontfamily(FONT_BODY)
    lbl.set_fontsize(9.5)

# Title
ax.set_title(
    "EDA: Class Imbalance Across 15 Conditions → 11 Production Models",
    pad=20, **_t(14))
ax.text(0.5, 1.025,
        "4 conditions dropped post-EDA  ·  data sparsity / leakage",
        transform=ax.transAxes, ha="center", va="bottom",
        fontsize=9, fontfamily=FONT_BODY, color=MUTED, fontstyle="italic")

# Legend
leg_elements = [
    mpatches.Patch(facecolor=VIOLET,      label="Production model  (>10%)"),
    mpatches.Patch(facecolor=LIME,        label="Needs SMOTE / class_weight  (3–10%)"),
    mpatches.Patch(facecolor=DROPPED_BAR, hatch="///", edgecolor="#9999AA",
                   label="Dropped post-EDA  (insufficient data / <3%)"),
]
leg = ax.legend(handles=leg_elements, loc="lower right",
                framealpha=0.95, facecolor=CARD, edgecolor=CARD_BORDER,
                fontsize=9, labelcolor=MUTED_DARK)
for t in leg.get_texts():
    t.set_fontfamily(FONT_BODY)

# Footnote
ax.text(0.01, -0.085,
        "n=7,437  ·  NHANES 2017–2019  ·  Post adult-filter cohort",
        transform=ax.transAxes, fontsize=7.5,
        fontfamily=FONT_BODY, color=MUTED, va="top", ha="left")

plt.tight_layout(pad=1.6)
plt.savefig("presentation_assets/class_imbalance.png",
            dpi=300, facecolor=BG, bbox_inches="tight")
plt.close()
print("✓  class_imbalance.png")


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH 3 — Scaling Necessity: Raw vs StandardScaled
# ══════════════════════════════════════════════════════════════════════════════

N = 1000
phys_act = np.concatenate([
    np.zeros(200),
    np.random.exponential(60, 500),
    np.random.normal(300, 80, 300),
]).clip(0, 700)[:N]
smoking = (np.random.rand(N) < 0.22).astype(float)

raw    = np.column_stack([phys_act, smoking])
scaled = StandardScaler().fit_transform(raw)

feature_names = ["Physical Activity\n(min/week)", "Smoking\n(binary 0/1)"]

fig, axes = plt.subplots(1, 2, figsize=(13, 6.2), facecolor=BG)
fig.suptitle("Why Feature Scaling Is Necessary: Incomparable Raw Ranges",
             y=1.03, **_t(14))

panel_data = [
    ("Raw Data",           [raw[:, 0],    raw[:, 1]],    "Original units"),
    ("StandardScaled Data",[scaled[:, 0], scaled[:, 1]], "Z-score  (mean = 0,  σ = 1)"),
]

box_colors = [VIOLET, LIME]

for ax, (title, data, ylabel) in zip(axes, panel_data):
    style_card_ax(ax)

    bp = ax.boxplot(
        data,
        patch_artist=True,
        medianprops=dict(color=NEAR_BLACK, linewidth=2.2),
        whiskerprops=dict(color=MUTED_DARK, linewidth=1.3),
        capprops=dict(color=MUTED_DARK, linewidth=1.3),
        flierprops=dict(marker="o", markerfacecolor=CARD_BORDER,
                        markeredgecolor=MUTED, markersize=3, alpha=0.5),
        widths=0.42,
    )
    for patch, col in zip(bp["boxes"], box_colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.82)
        patch.set_edgecolor(NEAR_BLACK)
        patch.set_linewidth(0.8)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(feature_names, fontsize=10, fontfamily=FONT_BODY,
                       color=NEAR_BLACK, linespacing=1.4)
    ax.set_ylabel(ylabel, fontsize=10, fontfamily=FONT_BODY,
                  color=MUTED_DARK, labelpad=8)
    ax.set_title(title, pad=12, **_t(12.5))
    ax.grid(axis="y", color=CARD_BORDER, linewidth=0.7, zorder=0)

    # Annotations on raw panel only
    if "Raw" in title:
        r_act = np.ptp(data[0])
        r_smk = np.ptp(data[1])
        ax.annotate(
            f"Range ≈ {r_act:.0f}",
            xy=(1, np.percentile(data[0], 96)),
            xytext=(1.22, np.percentile(data[0], 96) * 0.88),
            fontsize=8.5, fontfamily=FONT_BODY, color=VIOLET,
            arrowprops=dict(arrowstyle="->", color=VIOLET, lw=1.3),
        )
        ax.annotate(
            f"Range = {r_smk:.0f}",
            xy=(2, 1.05),
            xytext=(1.62, np.percentile(data[0], 60) * 0.55),
            fontsize=8.5, fontfamily=FONT_BODY, color=MUTED_DARK,
            arrowprops=dict(arrowstyle="->", color=MUTED_DARK, lw=1.3),
        )

# Shared legend
v_patch = mpatches.Patch(facecolor=VIOLET, edgecolor=NEAR_BLACK, linewidth=0.8,
                          label="Physical Activity (min/week)")
l_patch = mpatches.Patch(facecolor=LIME,   edgecolor=NEAR_BLACK, linewidth=0.8,
                          label="Smoking (binary 0/1)")
leg = fig.legend(handles=[v_patch, l_patch], loc="lower center",
                 ncol=2, framealpha=0.95, facecolor=CARD, edgecolor=CARD_BORDER,
                 fontsize=9.5, labelcolor=MUTED_DARK,
                 bbox_to_anchor=(0.5, -0.04))
for t in leg.get_texts():
    t.set_fontfamily(FONT_BODY)

plt.tight_layout(pad=1.6)
plt.savefig("presentation_assets/scaling_necessity.png",
            dpi=300, facecolor=BG, bbox_inches="tight")
plt.close()
print("✓  scaling_necessity.png")

print("\nAll 3 CI-aligned plots saved to presentation_assets/")
