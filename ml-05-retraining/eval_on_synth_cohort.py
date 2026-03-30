"""
eval_on_synth_cohort.py
------------------------
ML-05: Evaluate the three retrained models against the existing synthetic
eval cohort (evals/cohort/profiles_v2_latent.json).

Uses the existing ModelRunner normalization pipeline so inputs pass through
the same HybridReferenceNormalizer as production inference. New model-specific
derived features (waist_elevated_*, bmi_x_family_dm) are added post-normalization.

Reports:
  - Top-1 / Top-3 accuracy per condition (kidney, inflammation, prediabetes)
  - Comparison against the current production models (v2/v3)
  - FP rate on non-target profiles for each of the three conditions

Saves to: ml-05-retraining/eval/synth_cohort_eval.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")

ROOT      = Path(__file__).resolve().parents[1]
EVALS_DIR = ROOT / "evals"
MODELS_DIR = ROOT / "models_normalized"
EVAL_OUT  = Path(__file__).resolve().parent / "eval" / "synth_cohort_eval.json"

sys.path.insert(0, str(ROOT))

# ── Use the existing cohort profile builder from score_profiles.py ─────────────
from evals.score_profiles import _build_answers, CONDITION_TO_MODEL_KEY  # noqa: E402

# ── Load the InputNormalizer from ModelRunner (handles full normalization) ──────
from models_normalized.model_runner import InputNormalizer, MODEL_REGISTRY  # noqa: E402

NORMALIZER = InputNormalizer(
    models_dir         = MODELS_DIR,
    normalizer_path    = ROOT / "models" / "nhanes_hybrid_normalizer.joblib",
    sentinel_meta_path = ROOT / "data" / "processed" / "normalized" / "nhanes_ml_ready_metadata.json",
)

# ── Load current production models (for comparison) ─────────────────────────────
PROD_KIDNEY  = joblib.load(MODELS_DIR / "kidney_lr_deduped17_L2_v2.joblib")
PROD_INFLAM  = joblib.load(MODELS_DIR / "hidden_inflammation_lr_deduped26_L2_v3.joblib")
PROD_PREDIA  = joblib.load(MODELS_DIR / "prediabetes_lr_deduped34_L2_C001_v2.joblib")

PROD_K_FEATS = json.loads((MODELS_DIR / "kidney_lr_deduped17_L2_v2_metadata.json").read_text())["features"]
PROD_I_FEATS = json.loads((MODELS_DIR / "hidden_inflammation_lr_deduped26_L2_v3_metadata.json").read_text())["features"]
PROD_P_FEATS = json.loads((MODELS_DIR / "prediabetes_lr_deduped34_L2_C001_v2_metadata.json").read_text())["features"]

# ── Load new retrained models ───────────────────────────────────────────────────
NEW_KIDNEY  = joblib.load(MODELS_DIR / "kidney_lr_v3_hard_neg.joblib")
NEW_INFLAM  = joblib.load(MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg.joblib")
NEW_PREDIA  = joblib.load(MODELS_DIR / "prediabetes_xgb_v3_hard_neg.joblib")

NEW_K_FEATS = json.loads((MODELS_DIR / "kidney_lr_v3_hard_neg_metadata.json").read_text())["features"]
NEW_I_FEATS = json.loads((MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg_metadata.json").read_text())["features"]
NEW_P_FEATS = json.loads((MODELS_DIR / "prediabetes_xgb_v3_hard_neg_metadata.json").read_text())["features"]


# ── Normalize a single profile to a full feature row ────────────────────────────

def normalize_profile(profile: dict) -> pd.Series:
    """
    Convert a cohort profile → normalized single-row pd.Series containing ALL
    available normalized columns (full normalizer output, not just registered
    model features). New derived features are added post-normalization.
    """
    answers  = _build_answers(profile)
    fv_dict  = NORMALIZER.build_feature_vectors(answers)

    # Reconstruct a full normalized row by merging all per-model feature dicts
    # (they all come from the same single normalized row, just different slices)
    full_row: dict = {}
    for feats_df in fv_dict.values():
        full_row.update(feats_df.iloc[0].to_dict())

    # Also run the normalizer directly to capture columns not in any current model
    import importlib
    norm_row = pd.Series(full_row)

    # ── Add new derived features ──────────────────────────────────────────────
    # waist flags for inflammation v4
    waist = float(norm_row.get("waist_cm", 0.0) or 0.0)
    gf    = float(norm_row.get("gender_female", 0.0) or 0.0)
    norm_row["waist_elevated_female"] = 1.0 if (gf == 1.0 and waist >= 0.35) else 0.0
    norm_row["waist_elevated_male"]   = 1.0 if (gf == 0.0 and waist >= 0.65) else 0.0

    # bmi × family_dm interaction for prediabetes v3
    bmi_val  = float(norm_row.get("bmi", 0.0) or 0.0)
    fam_dm   = norm_row.get("mcq300c___close_relative_had_diabetes", np.nan)
    fam_flag = 1.0 if (not pd.isna(fam_dm) and float(fam_dm) == 1.0) else 0.0
    norm_row["bmi_x_family_dm"] = bmi_val * fam_flag

    return norm_row


def score_from_row(model, row: pd.Series, features: list[str]) -> float:
    """Score a single normalized row with a model."""
    X = pd.DataFrame([{f: row.get(f, np.nan) for f in features}])
    return float(model.predict_proba(X)[0, 1])


# ── Load cohort ──────────────────────────────────────────────────────────────────

COHORT_PATH = EVALS_DIR / "cohort" / "profiles_v2_latent.json"
if not COHORT_PATH.exists():
    COHORT_PATH = EVALS_DIR / "cohort" / "profiles.json"

print(f"Loading cohort from: {COHORT_PATH}")
profiles = json.loads(COHORT_PATH.read_text())
print(f"Loaded {len(profiles)} profiles")


# ── Scoring loop ─────────────────────────────────────────────────────────────────

TARGET_CONDITIONS = {"kidney_disease", "inflammation", "prediabetes"}

records = []
for i, profile in enumerate(profiles):
    target = profile.get("target_condition", "unknown")
    try:
        row = normalize_profile(profile)
    except Exception as e:
        print(f"  [WARN] Profile {i} ({target}): normalization failed — {e}")
        continue

    rec = {
        "target": target,
        "model_key": CONDITION_TO_MODEL_KEY.get(target),
    }

    # Production scores
    rec["prod_kidney_score"]  = score_from_row(PROD_KIDNEY,  row, PROD_K_FEATS)
    rec["prod_inflam_score"]  = score_from_row(PROD_INFLAM,  row, PROD_I_FEATS)
    rec["prod_predia_score"]  = score_from_row(PROD_PREDIA,  row, PROD_P_FEATS)

    # New model scores
    rec["new_kidney_score"]   = score_from_row(NEW_KIDNEY,   row, NEW_K_FEATS)
    rec["new_inflam_score"]   = score_from_row(NEW_INFLAM,   row, NEW_I_FEATS)
    rec["new_predia_score"]   = score_from_row(NEW_PREDIA,   row, NEW_P_FEATS)

    records.append(rec)

    if (i + 1) % 50 == 0:
        print(f"  Scored {i+1}/{len(profiles)} profiles...")

df = pd.DataFrame(records)
print(f"\nScored {len(df)} profiles successfully.")


# ── Compute metrics ───────────────────────────────────────────────────────────────

def top_k_acc(df_sub: pd.DataFrame, model_col: str, competing_cols: list[str], k: int) -> float:
    hits = 0
    for _, row in df_sub.iterrows():
        all_scores = [row[model_col]] + [row[c] for c in competing_cols]
        rank = sorted(all_scores, reverse=True).index(row[model_col]) + 1
        if rank <= k:
            hits += 1
    return hits / len(df_sub) if len(df_sub) > 0 else 0.0


def fp_rate(df_non_target: pd.DataFrame, score_col: str, thr: float = 0.35) -> float:
    return float((df_non_target[score_col] >= thr).mean()) if len(df_non_target) > 0 else 0.0


results = {}

for label, condition_key, prod_col, new_col, prod_comp, new_comp in [
    (
        "kidney",
        "kidney_disease",
        "prod_kidney_score", "new_kidney_score",
        ["prod_inflam_score", "prod_predia_score"],
        ["new_inflam_score",  "new_predia_score"],
    ),
    (
        "inflammation",
        "inflammation",
        "prod_inflam_score", "new_inflam_score",
        ["prod_kidney_score", "prod_predia_score"],
        ["new_kidney_score",  "new_predia_score"],
    ),
    (
        "prediabetes",
        "prediabetes",
        "prod_predia_score", "new_predia_score",
        ["prod_kidney_score", "prod_inflam_score"],
        ["new_kidney_score",  "new_inflam_score"],
    ),
]:
    pos = df[df["target"] == condition_key]
    neg = df[df["target"] != condition_key]

    if len(pos) == 0:
        print(f"  [WARN] No profiles found for {condition_key}")
        continue

    results[label] = {
        "n_positives": len(pos),
        "n_negatives": len(neg),
        "production": {
            "top_1_acc": round(top_k_acc(pos, prod_col, prod_comp, 1), 4),
            "top_3_acc": round(top_k_acc(pos, prod_col, prod_comp, 3), 4),
            "mean_score_pos":    round(float(pos[prod_col].mean()), 4),
            "fp_rate_neg_thr035": round(fp_rate(neg, prod_col), 4),
        },
        "retrained": {
            "top_1_acc": round(top_k_acc(pos, new_col, new_comp, 1), 4),
            "top_3_acc": round(top_k_acc(pos, new_col, new_comp, 3), 4),
            "mean_score_pos":    round(float(pos[new_col].mean()), 4),
            "fp_rate_neg_thr035": round(fp_rate(neg, new_col), 4),
        },
    }

# ── Print summary ────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  Synthetic Cohort Eval — ML-05 (v2_latent cohort)")
print("=" * 65)
print(f"{'Model':<16} {'Version':<12} {'Top-1':>7} {'Top-3':>7} {'Mean+':>7} {'FP@0.35':>8}")
print("-" * 65)

for cond, res in results.items():
    p = res["production"]
    r = res["retrained"]
    print(f"{cond:<16} {'production':<12} {p['top_1_acc']:>7.1%} {p['top_3_acc']:>7.1%} {p['mean_score_pos']:>7.3f} {p['fp_rate_neg_thr035']:>8.1%}")
    print(f"{'':<16} {'retrained':<12} {r['top_1_acc']:>7.1%} {r['top_3_acc']:>7.1%} {r['mean_score_pos']:>7.3f} {r['fp_rate_neg_thr035']:>8.1%}")
    print()

# ── Save ─────────────────────────────────────────────────────────────────────────

output = {
    "cohort_file": str(COHORT_PATH.name),
    "n_profiles_total": len(profiles),
    "n_profiles_scored": len(df),
    "date": "2026-03-30",
    "results": results,
}

EVAL_OUT.write_text(json.dumps(output, indent=2))
print(f"Results saved → {EVAL_OUT}")
