"""
Calibration Evaluation: Brier Score + Reliability Diagrams
===========================================================
Models evaluated:
  - thyroid_lr_l2_18feat
  - inflammation_lr_l2_32feat
  - electrolyte_imbalance_logreg_final_quiz

Goal:
  Brier score < 0.15 and calibration curve R² > 0.85.
  Miscalibrated models give MedGemma false confidence inputs.

Output:
  evaluation/calibration_report.png
  evaluation/calibration_summary.csv
"""

import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")  # non-interactive — prevents blocking on plt.show()

import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from sklearn.metrics import brier_score_loss
from sklearn.calibration import calibration_curve
from sklearn.model_selection import train_test_split

SEED = 42
DATA_PATH = "data/processed/nhanes_merged_adults_final.csv"
OUT_DIR = Path("evaluation")
OUT_DIR.mkdir(exist_ok=True)

# ── Utilities ──────────────────────────────────────────────────────────────

def add_miss_flags(df_feat, flag_cols):
    """Add binary _miss indicator columns for a specified list of features."""
    flags = {f"{c}_miss": df_feat[c].isnull().astype(float)
             for c in flag_cols if c in df_feat.columns}
    return pd.concat([df_feat, pd.DataFrame(flags, index=df_feat.index)], axis=1)


def encode_categoricals(df, target_col):
    """Encode object/category columns with pandas Categorical codes (–1 → NaN)."""
    df = df.copy()
    for col in df.select_dtypes(include=["object", "category"]).columns:
        if col == target_col:
            continue
        codes = pd.Categorical(df[col]).codes
        df[col] = pd.Series(codes.astype(float), index=df.index).replace(-1, np.nan)
    return df


def calibration_r2(prob_true, prob_pred):
    """
    Pearson R² of (prob_pred, prob_true) calibration curve bins.
    Measures how linearly correlated the bin means are (monotonicity of calibration).
    A value close to 1 means the model ranks probabilities in the right order.
    Does NOT measure absolute bias — use Brier score for that.
    """
    mask = ~(np.isnan(prob_true) | np.isnan(prob_pred))
    if mask.sum() < 2:
        return np.nan
    pt, pp = prob_true[mask], prob_pred[mask]
    if np.std(pt) == 0 or np.std(pp) == 0:
        return np.nan
    r = np.corrcoef(pp, pt)[0, 1]
    return r ** 2


def reliability_plot(ax, y_true, y_prob, title, n_bins=10):
    """
    Draw a reliability diagram on ax.
    Bins: [0,0.1), [0.1,0.2), … [0.9,1.0]
    Returns (brier_score, r2, mean_prob, prevalence).
    """
    bs = brier_score_loss(y_true, y_prob)
    prevalence = y_true.mean()
    mean_prob = y_prob.mean()

    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")
    r2 = calibration_r2(prob_true, prob_pred)

    # Bar chart of bin counts (background)
    bins = np.linspace(0, 1, n_bins + 1)
    bin_counts, _ = np.histogram(y_prob, bins=bins)
    bar_ax = ax.twinx()
    bar_ax.bar(
        (bins[:-1] + bins[1:]) / 2,
        bin_counts,
        width=0.088,
        alpha=0.18,
        color="steelblue",
        label="Sample count",
    )
    bar_ax.set_ylabel("Sample count", color="steelblue", fontsize=7)
    bar_ax.tick_params(axis="y", labelcolor="steelblue", labelsize=7)
    bar_ax.set_ylim(0, max(bin_counts) * 5)  # push bars to bottom fifth

    # Perfect calibration diagonal
    ax.plot([0, 1], [0, 1], "k--", lw=1.2, label="Perfect calibration", zorder=3)

    # Calibration curve
    r2_label = f"{r2:.3f}" if not np.isnan(r2) else "N/A"
    ax.plot(
        prob_pred,
        prob_true,
        "o-",
        color="#e74c3c",
        lw=2,
        ms=7,
        markerfacecolor="white",
        markeredgewidth=2,
        label=f"Model (R²={r2_label})",
        zorder=4,
    )

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Mean predicted probability", fontsize=9)
    ax.set_ylabel("Fraction of positives", fontsize=9)

    # Title includes key stats
    r2_str = f"{r2:.3f}" if not np.isnan(r2) else "N/A"
    ax.set_title(
        f"{title}\nBrier={bs:.4f}   Calib R²={r2_str}",
        fontsize=10,
        fontweight="bold",
        pad=6,
    )

    # Pass/fail badges
    bs_ok = bs < 0.15
    r2_ok = (not np.isnan(r2)) and r2 > 0.85
    badge_text = (
        f"{'✓' if bs_ok else '✗'} Brier < 0.15\n"
        f"{'✓' if r2_ok else '✗'} R²   > 0.85"
    )
    badge_color = "#2ecc71" if (bs_ok and r2_ok) else "#e74c3c"
    ax.text(
        0.03, 0.97, badge_text,
        transform=ax.transAxes,
        va="top", ha="left",
        fontsize=8, fontfamily="monospace",
        color=badge_color, fontweight="bold",
    )

    # Bias annotation: mean predicted vs actual prevalence
    bias = mean_prob - prevalence
    ax.text(
        0.97, 0.03,
        f"Prev={prevalence:.3f}\nMean p̂={mean_prob:.3f}\nBias={bias:+.3f}",
        transform=ax.transAxes,
        va="bottom", ha="right",
        fontsize=7.5, fontfamily="monospace",
        color="#555",
        bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="#bbb", alpha=0.8),
    )

    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    return bs, r2, mean_prob, prevalence


# ══════════════════════════════════════════════════════════════════════════════
# 1. THYROID
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("Loading data …")
df_raw = pd.read_csv(DATA_PATH, low_memory=False)
print(f"  Raw shape: {df_raw.shape}")

print("\n[1/3] THYROID")

THYROID_COL_MAP = {
    "age_years":              "age_years",
    "gender":                 "gender",
    "med_count":              "med_count",
    "avg_drinks_per_day":     "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "general_health_condition": "huq010___general_health_condition",
    "doctor_said_overweight": "mcq080___doctor_ever_said_you_were_overweight",
    "told_dr_trouble_sleeping": "slq050___ever_told_doctor_had_trouble_sleeping?",
    "tried_to_lose_weight":   "whq070___tried_to_lose_weight_in_past_year",
    "avg_cigarettes_per_day": "smd650___avg_#_cigarettes/day_during_past_30_days",
    "weight_kg":              "weight_kg",
    "pregnancy_status":       "pregnancy_status",
    "moderate_recreational":  "paq665___moderate_recreational_activities",
    "times_urinate_in_night": "kiq480___how_many_times_urinate_in_night?",
    "overall_work_schedule":  "ocq670___overall_work_schedule_past_3_months",
    "ever_told_high_cholesterol": "bpq080___doctor_told_you___high_cholesterol_level",
    "ever_told_diabetes":     "diq010___doctor_told_you_have_diabetes",
    "taking_anemia_treatment": "mcq053___taking_treatment_for_anemia/past_3_mos",
    "sleep_hours_weekdays":   "sld012___sleep_hours___weekdays_or_workdays",
    "thyroid":                "thyroid",
}

THYROID_MISS_FLAGS = [
    "avg_drinks_per_day", "tried_to_lose_weight", "avg_cigarettes_per_day",
    "weight_kg", "times_urinate_in_night", "overall_work_schedule", "sleep_hours_weekdays",
]

_valid = {k: v for k, v in THYROID_COL_MAP.items() if v in df_raw.columns}
df_t = df_raw[[v for v in _valid.values()]].copy()
df_t.columns = list(_valid.keys())
df_t = df_t.dropna(subset=["thyroid"])
df_t["thyroid"] = df_t["thyroid"].astype(int)

BASE_FEATS_T = [k for k in THYROID_COL_MAP if k != "thyroid"]
BASE_FEATS_T = [f for f in BASE_FEATS_T if f in df_t.columns]

df_t = encode_categoricals(df_t, "thyroid")
df_t = add_miss_flags(df_t, THYROID_MISS_FLAGS)
ALL_FEATS_T = BASE_FEATS_T + [f"{c}_miss" for c in THYROID_MISS_FLAGS if f"{c}_miss" in df_t.columns]

X_t = df_t[ALL_FEATS_T]
y_t = df_t["thyroid"]

_, X_test_t, _, y_test_t = train_test_split(
    X_t, y_t, test_size=0.2, stratify=y_t, random_state=SEED
)

model_t = joblib.load("models/thyroid_lr_l2_18feat.joblib")
y_prob_t = model_t.predict_proba(X_test_t)[:, 1]
print(f"  Test set: n={len(y_test_t)}, positives={y_test_t.sum()} ({y_test_t.mean()*100:.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# 2. INFLAMMATION
# ══════════════════════════════════════════════════════════════════════════════

print("\n[2/3] INFLAMMATION")

INF_COL_MAP = {
    "total_cholesterol":   "LBXTC_total_cholesterol_mg_dl",
    "ldl_cholesterol":     "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
    "hdl_cholesterol":     "LBDHDD_direct_hdl_cholesterol_mg_dl",
    "triglycerides":       "LBXTR_triglyceride_mg_dl",
    "serum_glucose":       "LBXSGL_glucose_refrigerated_serum_mg_dl",
    "fasting_glucose":     "LBXGLU_fasting_glucose_mg_dl",
    "creatinine":          "LBXSCR_creatinine_refrigerated_serum_mg_dl",
    "sbp_1": "sbp_1", "sbp_2": "sbp_2", "sbp_3": "sbp_3",
    "dbp_1": "dbp_1", "dbp_2": "dbp_2", "dbp_3": "dbp_3",
    "pulse_1": "pulse_1", "pulse_2": "pulse_2", "pulse_3": "pulse_3",
    "bmi":                 "bmi",
    "calcium":             "LBXSCA_total_calcium_mg_dl",
    "age_years":           "age_years",
    "smoking_now":         "smq040___do_you_now_smoke_cigarettes?",
    "cigarettes_per_day":  "smd650___avg_#_cigarettes/day_during_past_30_days",
    "avg_drinks_per_day":  "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "ever_heavy_drinker":  "alq151___ever_have_4/5_or_more_drinks_every_day?",
    "sedentary_minutes":   "pad680___minutes_sedentary_activity",
    "vigorous_exercise":   "paq650___vigorous_recreational_activities",
    "moderate_exercise":   "paq665___moderate_recreational_activities",
    "sleep_hours_weekdays": "sld012___sleep_hours___weekdays_or_workdays",
    "told_dr_trouble_sleeping": "slq050___ever_told_doctor_had_trouble_sleeping?",
    "work_schedule":       "ocq670___overall_work_schedule_past_3_months",
    "hours_worked_per_week": "ocq180___hours_worked_last_week_in_total_all_jobs",
    "diabetes":            "diq010___doctor_told_you_have_diabetes",
    "doctor_said_overweight": "mcq080___doctor_ever_said_you_were_overweight",
    "liver_condition":     "mcq160l___ever_told_you_had_any_liver_condition",
    "kidney_disease":      "kiq022___ever_told_you_had_weak/failing_kidneys?",
    "regular_periods":     "rhq031___had_regular_periods_in_past_12_months",
    "general_health_condition": "huq010___general_health_condition",
    "waist_cm":            "waist_cm",
    "gender":              "gender",
    "infection_inflammation": "infection_inflammation",
}

INF_MISS_FLAGS = [
    "total_cholesterol", "ldl_cholesterol", "hdl_cholesterol", "triglycerides",
    "serum_glucose", "fasting_glucose", "creatinine",
    "sbp_mean", "dbp_mean", "pulse_mean",
    "bmi", "calcium",
    "smoking_now", "cigarettes_per_day", "avg_drinks_per_day", "ever_heavy_drinker",
    "sedentary_minutes", "sleep_hours_weekdays", "work_schedule", "hours_worked_per_week",
    "liver_condition", "kidney_disease", "regular_periods", "waist_cm",
]

_valid_i = {k: v for k, v in INF_COL_MAP.items() if v in df_raw.columns}
df_i = df_raw[[v for v in _valid_i.values()]].copy()
df_i.columns = list(_valid_i.keys())

# Average BP/pulse
for pfx in ["sbp", "dbp", "pulse"]:
    cs = [c for c in df_i.columns if c.startswith(f"{pfx}_")]
    if cs:
        df_i[f"{pfx}_mean"] = df_i[cs].mean(axis=1)
        df_i.drop(columns=cs, inplace=True)

df_i = df_i.dropna(subset=["infection_inflammation"])
df_i["infection_inflammation"] = df_i["infection_inflammation"].astype(int)
df_i = encode_categoricals(df_i, "infection_inflammation")

BASE_FEATS_I = [
    "total_cholesterol", "ldl_cholesterol", "hdl_cholesterol", "triglycerides",
    "serum_glucose", "fasting_glucose", "creatinine",
    "sbp_mean", "dbp_mean", "pulse_mean",
    "bmi", "calcium", "age_years",
    "smoking_now", "cigarettes_per_day", "avg_drinks_per_day", "ever_heavy_drinker",
    "sedentary_minutes", "vigorous_exercise", "moderate_exercise",
    "sleep_hours_weekdays", "told_dr_trouble_sleeping", "work_schedule",
    "hours_worked_per_week", "diabetes", "doctor_said_overweight", "liver_condition",
    "kidney_disease", "regular_periods", "general_health_condition", "waist_cm", "gender",
]
BASE_FEATS_I = [f for f in BASE_FEATS_I if f in df_i.columns]

df_i = add_miss_flags(df_i, [f for f in INF_MISS_FLAGS if f in df_i.columns])
ALL_FEATS_I = BASE_FEATS_I + [
    f"{c}_miss" for c in INF_MISS_FLAGS if f"{c}_miss" in df_i.columns
]

X_i = df_i[ALL_FEATS_I]
y_i = df_i["infection_inflammation"]

_, X_test_i, _, y_test_i = train_test_split(
    X_i, y_i, test_size=0.2, stratify=y_i, random_state=SEED
)

model_i = joblib.load("models/inflammation_lr_l2_32feat.joblib")
y_prob_i = model_i.predict_proba(X_test_i)[:, 1]
print(f"  Test set: n={len(y_test_i)}, positives={y_test_i.sum()} ({y_test_i.mean()*100:.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# 3. ELECTROLYTE IMBALANCE
# ══════════════════════════════════════════════════════════════════════════════

print("\n[3/3] ELECTROLYTE IMBALANCE")

EI_FEATURES = [
    "bpq020___ever_told_you_had_high_blood_pressure",
    "kiq480___how_many_times_urinate_in_night?",
    "paq650___vigorous_recreational_activities",
    "med_count",
    "dpq040___feeling_tired_or_having_little_energy",
    "kiq026___ever_had_kidney_stones?",
    "mcq160a___ever_told_you_had_arthritis",
    "kiq022___ever_told_you_had_weak/failing_kidneys?",
]
EI_TARGET = "electrolyte_imbalance"

ei_cols = EI_FEATURES + [EI_TARGET]
df_e = df_raw[[c for c in ei_cols if c in df_raw.columns]].copy()
df_e = df_e.dropna(subset=[EI_TARGET])
df_e[EI_TARGET] = df_e[EI_TARGET].astype(int)

present_feats_e = [f for f in EI_FEATURES if f in df_e.columns]
X_e = df_e[present_feats_e]
y_e = df_e[EI_TARGET]

_, X_test_e, _, y_test_e = train_test_split(
    X_e, y_e, test_size=0.2, stratify=y_e, random_state=SEED
)

model_e = joblib.load("models/electrolyte_imbalance_logreg_final_quiz.joblib")
y_prob_e = model_e.predict_proba(X_test_e)[:, 1]
print(f"  Test set: n={len(y_test_e)}, positives={y_test_e.sum()} ({y_test_e.mean()*100:.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# PLOT
# ══════════════════════════════════════════════════════════════════════════════

print("\nGenerating calibration report …")

fig = plt.figure(figsize=(18, 7))
fig.suptitle(
    "Model Calibration Report — Reliability Diagrams (10-bin uniform)\n"
    "Goal: Brier < 0.15 | Calibration R² > 0.85",
    fontsize=13, fontweight="bold", y=1.01,
)

gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.38)
axes = [fig.add_subplot(gs[0, i]) for i in range(3)]

results = []

configs = [
    ("Thyroid\n(18 quest. features)", y_test_t, y_prob_t, "thyroid_lr_l2_18feat"),
    ("Inflammation\n(32 lab+quest. features)", y_test_i, y_prob_i, "inflammation_lr_l2_32feat"),
    ("Electrolyte Imbalance\n(8 quiz features)", y_test_e, y_prob_e, "electrolyte_imbalance_logreg_final_quiz"),
]

for ax, (title, y_true, y_prob, model_name) in zip(axes, configs):
    bs, r2, mean_prob, prevalence = reliability_plot(ax, y_true.values, y_prob, title)
    results.append({
        "model": model_name,
        "n_test": len(y_true),
        "prevalence_pct": round(prevalence * 100, 2),
        "mean_predicted_prob": round(mean_prob, 4),
        "bias": round(mean_prob - prevalence, 4),
        "brier_score": round(bs, 5),
        "calibration_r2": round(r2, 5) if not np.isnan(r2) else None,
        "brier_pass": bs < 0.15,
        "r2_pass": (not np.isnan(r2)) and r2 > 0.85,
    })

fig.text(
    0.5, -0.04,
    "Note: All models trained with class_weight='balanced' — predicted probabilities are systematically inflated above natural prevalence.\n"
    "Brier score penalises both overconfidence and underconfidence. R² measures monotonic linearity of calibration bins (Pearson R² of 10 uniform bins).\n"
    "High R² + high Brier = correctly ordered but biased predictions. Platt scaling or isotonic regression can correct the bias post-hoc.",
    ha="center", va="top", fontsize=8, color="#555", style="italic",
    transform=fig.transFigure,
)

plt.tight_layout()
out_png = OUT_DIR / "calibration_report.png"
fig.savefig(out_png, dpi=150, bbox_inches="tight")
print(f"  Saved → {out_png}")

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════

df_results = pd.DataFrame(results)
out_csv = OUT_DIR / "calibration_summary.csv"
df_results.to_csv(out_csv, index=False)

print("\n" + "=" * 60)
print("CALIBRATION SUMMARY")
print("=" * 60)
print(df_results.to_string(index=False))
print("=" * 60)

for row in results:
    bs_flag = "✓ PASS" if row["brier_pass"] else "✗ FAIL"
    r2_flag = "✓ PASS" if row["r2_pass"] else "✗ FAIL"
    r2_val = f"{row['calibration_r2']:.4f}" if row["calibration_r2"] is not None else "N/A"
    print(
        f"  {row['model'][:40]:<40}"
        f"  Brier={row['brier_score']:.4f} {bs_flag}"
        f"  R²={r2_val} {r2_flag}"
    )

print(f"\nResults saved to {OUT_DIR}/")
plt.show()
