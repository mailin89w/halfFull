"""
evaluate_post_retraining.py
----------------------------
ML-05: Post-retraining evaluation against real NHANES holdout samples +
synthetic hard-negative controls.

Positive test cases: 20% stratified holdout from the normalized NHANES CSV
  (same split seed=42 as training — evaluates on held-out REAL samples)

Hard-negative controls: 200 synthetic fatigue-only profiles + 50 sleep + 50 thyroid
  Scored at threshold 0.35 for FP rate.

Saves results to ml-05-retraining/eval/post_retraining_results.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split

ROOT       = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models_normalized"
EVAL_DIR   = Path(__file__).resolve().parent / "eval"
DATA_PATH  = ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"
OUTPUT_PATH = EVAL_DIR / "post_retraining_results.json"

EVAL_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

RNG  = np.random.default_rng(42)
SEED = 42

_EDU_ORDER = {
    "Less than 9th grade":       0,
    "9-11th grade":              1,
    "High school / GED":         2,
    "Some college / AA":         3,
    "College graduate or above": 4,
}


def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["gender_female"] = np.where(df["gender"].eq("Female"), 1.0,
                          np.where(df["gender"].isna(), np.nan, 0.0))
    if "education" in df.columns and "education_ord" not in df.columns:
        df["education_ord"] = df["education"].map(_EDU_ORDER)
    if "pregnancy_status_bin" not in df.columns:
        df["pregnancy_status_bin"] = np.where(
            df["pregnancy_status"].eq("Yes, pregnant"), 1.0, 0.0
        )
    waist = df["waist_cm"].fillna(0.0)
    is_female = df["gender_female"].fillna(0.0)
    df["waist_elevated_female"] = ((is_female == 1) & (waist >= 0.35)).astype(float)
    df["waist_elevated_male"]   = ((is_female == 0) & (waist >= 0.65)).astype(float)
    bmi    = df.get("bmi", pd.Series(np.nan, index=df.index))
    fam_dm = df.get("mcq300c___close_relative_had_diabetes", pd.Series(np.nan, index=df.index))
    fam_dm_bin = fam_dm.apply(
        lambda v: 1.0 if (not pd.isna(v) and int(v) == 1) else 0.0 if not pd.isna(v) else 0.0
    )
    df["bmi_x_family_dm"] = bmi.fillna(0.0) * fam_dm_bin
    return df


# ── Load new models ──────────────────────────────────────────────────────────────

KIDNEY_MODEL = joblib.load(MODELS_DIR / "kidney_lr_v3_hard_neg.joblib")
KIDNEY_META  = json.loads((MODELS_DIR / "kidney_lr_v3_hard_neg_metadata.json").read_text())
KIDNEY_FEATS = KIDNEY_META["features"]

INFLAM_MODEL = joblib.load(MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg.joblib")
INFLAM_META  = json.loads((MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg_metadata.json").read_text())
INFLAM_FEATS = INFLAM_META["features"]

PREDIA_MODEL = joblib.load(MODELS_DIR / "prediabetes_xgb_v3_hard_neg.joblib")
PREDIA_META  = json.loads((MODELS_DIR / "prediabetes_xgb_v3_hard_neg_metadata.json").read_text())
PREDIA_FEATS = PREDIA_META["features"]


# ── Hard-negative generator (normalized feature space) ────────────────────────────

def _ri(lo, hi, size=None):
    return RNG.integers(lo, hi + 1, size=size).astype(float)

def _ru(lo, hi, size=None):
    return RNG.uniform(lo, hi, size)


def gen_hard_negatives_normalized(n_fatigue=100, n_sleep=50, n_thyroid=50) -> pd.DataFrame:
    """Generate hard-negative profiles using all necessary features (no NaNs for key fields)."""
    def _base(n, age_lo=25, age_hi=55):
        return pd.DataFrame({
            # Kidney features
            "uacr_mg_g":                                      _ru(-0.27, 0.1, n),
            "serum_creatinine_mg_dl":                         _ru(-1.0, 0.0, n),
            "LBXSUA_uric_acid_mg_dl":                         _ru(-1.0, 0.3, n),
            "age_years":                                      _ri(age_lo, age_hi, n),
            "med_count":                                      _ru(-0.66, -0.31, n),
            "huq010___general_health_condition":              _ri(2, 4, n),
            "huq071___overnight_hospital_patient_in_last_year": np.full(n, 2.0),
            "kiq005___how_often_have_urinary_leakage?":       _ri(3, 5, n),
            "kiq480___how_many_times_urinate_in_night?":      _ri(0, 1, n),
            "mcq160b___ever_told_you_had_congestive_heart_failure": np.full(n, 2.0),
            "mcq160a___ever_told_you_had_arthritis":          np.full(n, 2.0),
            "mcq092___ever_receive_blood_transfusion":        np.full(n, 2.0),
            "mcq520___abdominal_pain_during_past_12_months?": np.full(n, 2.0),
            "cdq010___shortness_of_breath_on_stairs/inclines": np.full(n, 2.0),
            "bpq020___ever_told_you_had_high_blood_pressure": np.full(n, 2.0),
            "paq650___vigorous_recreational_activities":      _ri(1, 2, n),
            "alq151___ever_have_4/5_or_more_drinks_every_day?": np.full(n, 2.0),
            "smq078___how_soon_after_waking_do_you_smoke":    np.full(n, 0.0),
            "whq040___like_to_weigh_more,_less_or_same":      _ri(2, 3, n),
            # Inflammation features
            "hdl_cholesterol_mg_dl":                          _ru(0.5, 2.5, n),
            "alq130___avg_#_alcoholic_drinks/day___past_12_mos": _ru(0, 1, n),
            "sld012___sleep_hours___weekdays_or_workdays":    _ri(6, 8, n),
            "rhq031___had_regular_periods_in_past_12_months": np.full(n, 2.0),
            "slq030___how_often_do_you_snore?":               _ri(1, 2, n),
            "bpq080___doctor_told_you___high_cholesterol_level": np.full(n, 2.0),
            "mcq053___taking_treatment_for_anemia/past_3_mos": np.full(n, 2.0),
            "smd650___avg_#_cigarettes/day_during_past_30_days": np.zeros(n),
            "bpq030___told_had_high_blood_pressure___2+_times": np.full(n, 2.0),
            "huq051___#times_receive_healthcare_over_past_year": _ri(0, 2, n),
            "kiq430___how_frequently_does_this_occur?":       np.full(n, 0.0),
            "mcq195___which_type_of_arthritis_was_it?":       np.full(n, 0.0),
            "mcq300c___close_relative_had_diabetes":          np.full(n, 2.0),
            "ocq180___hours_worked_last_week_in_total_all_jobs": _ri(35, 45, n),
            "pregnancy_status_bin":                           np.zeros(n),
            "rhq131___ever_been_pregnant?":                   np.full(n, 2.0),
            "rhq160___how_many_times_have_been_pregnant?":    np.zeros(n),
            "smq020___smoked_at_least_100_cigarettes_in_life": np.full(n, 2.0),
            "smq040___do_you_now_smoke_cigarettes?":          np.full(n, 3.0),
            "waist_cm":                                       _ru(-0.2, 0.3, n),
            "waist_elevated_female":                          np.zeros(n),
            "waist_elevated_male":                            np.zeros(n),
            # Prediabetes features
            "mcq366d___doctor_told_to_reduce_fat_in_diet":    np.full(n, 2.0),
            "LBDLDL_ldl_cholesterol_friedewald_mg_dl":        _ru(-0.5, 0.5, n),
            "fasting_glucose_mg_dl":                          _ru(-0.5, 0.0, n),
            "bpq050a___now_taking_prescribed_medicine_for_hbp": np.full(n, 2.0),
            "paq665___moderate_recreational_activities":      _ri(1, 2, n),
            "paq620___moderate_work_activity":                _ri(1, 2, n),
            "whq070___tried_to_lose_weight_in_past_year":      np.full(n, 2.0),
            "mcq010___ever_been_told_you_have_asthma":         np.full(n, 2.0),
            "slq050___ever_told_doctor_had_trouble_sleeping?": np.full(n, 2.0),
            "dpq040___feeling_tired_or_having_little_energy":  _ri(1, 3, n),
            "education_ord":                                   _ri(2, 4, n),
            "kiq052___how_much_were_daily_activities_affected?": _ri(1, 2, n),
            "kiq022___ever_told_you_had_weak/failing_kidneys?": np.full(n, 2.0),
            "gender_female":                                   _ri(0, 1, n),
            "bmi":                                             _ru(-0.5, 0.5, n),
            "bmi_x_family_dm":                                 np.zeros(n),
        })

    fatigue = _base(n_fatigue)
    sleep   = _base(n_sleep)
    sleep["sld012___sleep_hours___weekdays_or_workdays"] = _ri(4, 6, n_sleep).astype(float)
    sleep["slq050___ever_told_doctor_had_trouble_sleeping?"] = 1.0
    sleep["slq030___how_often_do_you_snore?"] = _ri(3, 4, n_sleep).astype(float)
    thyroid = _base(n_thyroid, age_lo=30, age_hi=60)
    thyroid["bmi"] = _ru(0.5, 1.5, n_thyroid)
    thyroid["huq010___general_health_condition"] = _ri(3, 4, n_thyroid).astype(float)

    return pd.concat([fatigue, sleep, thyroid], ignore_index=True)


# ── Scoring helpers ──────────────────────────────────────────────────────────────

def _prep(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    for f in features:
        if f not in df.columns:
            df[f] = float("nan")
    return df[features]


def score_model(model, df: pd.DataFrame, features: list[str]) -> np.ndarray:
    return model.predict_proba(_prep(df.copy(), features))[:, 1]


def compute_top_k(pos_scores, competing_list, k):
    n = len(pos_scores)
    hits = sum(
        1 for i in range(n)
        if sorted([pos_scores[i]] + [s[i] for s in competing_list], reverse=True).index(pos_scores[i]) + 1 <= k
    )
    return hits / n


def fp_rate(scores, threshold=0.35):
    return float((np.asarray(scores) >= threshold).mean())


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Post-Retraining Evaluation — ML-05")
    print("=" * 60)

    # ── Load and prepare real NHANES data ────────────────────────────────────────
    df_full = pd.read_csv(DATA_PATH, low_memory=False)
    df_full = prepare_df(df_full)
    print(f"Loaded: {df_full.shape[0]:,} rows")

    # Stratified 80/20 split by kidney label (same seed as training)
    # We use the combined label for stratification
    y_kidney = df_full["kidney"].fillna(0).astype(int)
    y_inflam = df_full["hidden_inflammation"].fillna(0).astype(int)
    y_predia = df_full["prediabetes"].fillna(0).astype(int)

    _, df_test_k = train_test_split(df_full, test_size=0.20, stratify=y_kidney, random_state=SEED)
    _, df_test_i = train_test_split(df_full, test_size=0.20, stratify=y_inflam, random_state=SEED)
    _, df_test_p = train_test_split(df_full, test_size=0.20, stratify=y_predia, random_state=SEED)

    # Extract positive test cases
    kidney_pos_df = df_test_k[df_test_k["kidney"] == 1].copy()
    inflam_pos_df = df_test_i[df_test_i["hidden_inflammation"] == 1].copy()
    predia_pos_df = df_test_p[df_test_p["prediabetes"] == 1].copy()

    # Negatives of other conditions for ranking comparison
    kidney_neg_df = df_test_k[df_test_k["kidney"] == 0].sample(n=min(500, (df_test_k["kidney"]==0).sum()), random_state=SEED)
    inflam_neg_df = df_test_i[df_test_i["hidden_inflammation"] == 0].sample(n=min(500, (df_test_i["hidden_inflammation"]==0).sum()), random_state=SEED)
    predia_neg_df = df_test_p[df_test_p["prediabetes"] == 0].sample(n=min(500, (df_test_p["prediabetes"]==0).sum()), random_state=SEED)

    print(f"Test positives — kidney: {len(kidney_pos_df)}, inflam: {len(inflam_pos_df)}, prediabetes: {len(predia_pos_df)}")

    # ── Score models on real positives ──────────────────────────────────────────
    # Kidney positives
    k_pos = score_model(KIDNEY_MODEL, kidney_pos_df, KIDNEY_FEATS)
    k_on_inflam_pos = score_model(KIDNEY_MODEL, inflam_pos_df, KIDNEY_FEATS)
    k_on_predia_pos = score_model(KIDNEY_MODEL, predia_pos_df, KIDNEY_FEATS)

    # Inflammation positives
    i_pos = score_model(INFLAM_MODEL, inflam_pos_df, INFLAM_FEATS)
    i_on_kidney_pos = score_model(INFLAM_MODEL, kidney_pos_df, INFLAM_FEATS)
    i_on_predia_pos = score_model(INFLAM_MODEL, predia_pos_df, INFLAM_FEATS)

    # Prediabetes positives
    p_pos = score_model(PREDIA_MODEL, predia_pos_df, PREDIA_FEATS)
    p_on_kidney_pos = score_model(PREDIA_MODEL, kidney_pos_df, PREDIA_FEATS)
    p_on_inflam_pos = score_model(PREDIA_MODEL, inflam_pos_df, PREDIA_FEATS)

    # ── Top-k: for each kidney positive, does kidney score rank top-k vs inflam/predia? ──
    kidney_top1 = compute_top_k(k_pos, [i_on_kidney_pos, p_on_kidney_pos], 1)
    kidney_top3 = compute_top_k(k_pos, [i_on_kidney_pos, p_on_kidney_pos], 3)

    inflam_top1 = compute_top_k(i_pos, [k_on_inflam_pos, p_on_inflam_pos], 1)
    inflam_top3 = compute_top_k(i_pos, [k_on_inflam_pos, p_on_inflam_pos], 3)

    predia_top1 = compute_top_k(p_pos, [k_on_predia_pos, i_on_predia_pos], 1)
    predia_top3 = compute_top_k(p_pos, [k_on_predia_pos, i_on_predia_pos], 3)

    # ── FP rate on real negatives ────────────────────────────────────────────────
    k_ctrl = score_model(KIDNEY_MODEL, kidney_neg_df, KIDNEY_FEATS)
    i_ctrl = score_model(INFLAM_MODEL, inflam_neg_df, INFLAM_FEATS)
    p_ctrl = score_model(PREDIA_MODEL, predia_neg_df, PREDIA_FEATS)

    # ── Synthetic hard-negative controls ────────────────────────────────────────
    print("\nGenerating synthetic hard-negative controls...")
    fatigue_neg  = gen_hard_negatives_normalized(100, 0, 0)   # fatigue-only (100)
    combined_neg = gen_hard_negatives_normalized(100, 50, 50) # fatigue+sleep+thyroid (200)

    k_hard_fat = score_model(KIDNEY_MODEL, fatigue_neg, KIDNEY_FEATS)
    i_hard_fat = score_model(INFLAM_MODEL, fatigue_neg, INFLAM_FEATS)
    p_hard_fat = score_model(PREDIA_MODEL, fatigue_neg, PREDIA_FEATS)

    k_hard = score_model(KIDNEY_MODEL, combined_neg, KIDNEY_FEATS)
    i_hard = score_model(INFLAM_MODEL, combined_neg, INFLAM_FEATS)
    p_hard = score_model(PREDIA_MODEL, combined_neg, PREDIA_FEATS)

    # ── Inflammation intercept ────────────────────────────────────────────────────
    try:
        cal_step = INFLAM_MODEL.named_steps["clf"]
        base_lr  = cal_step.calibrated_classifiers_[0].estimator
        inflam_intercept = float(base_lr.intercept_[0])
    except Exception:
        inflam_intercept = float("nan")

    # ── Prediabetes flag rate on the NHANES positive test set ───────────────────
    PREDIA_THR   = PREDIA_META.get("recommended_threshold", 0.65)
    predia_flag  = float((score_model(PREDIA_MODEL, df_test_p, PREDIA_FEATS) >= PREDIA_THR).mean())

    # ── Definition of Done ────────────────────────────────────────────────────────
    # DoD uses fatigue-only profiles for the <5% FP target (per ML-05 ticket Task 4)
    dod = {
        "kidney_top1_gte_20pct":                      kidney_top1 >= 0.20,
        "kidney_top3_gte_60pct":                      kidney_top3 >= 0.60,
        "inflammation_top3_gte_55pct":                inflam_top3 >= 0.55,
        "inflammation_intercept_lt_05":               (not np.isnan(inflam_intercept)) and inflam_intercept < 0.5,
        "prediabetes_top1_gte_15pct":                 predia_top1 >= 0.15,
        "prediabetes_flag_rate_lt_20pct":             predia_flag  < 0.20,
        "kidney_fp_fatigue_only_lt5pct":              fp_rate(k_hard_fat) < 0.05,
        "inflammation_fp_fatigue_only_lt5pct":        fp_rate(i_hard_fat) < 0.05,
        "prediabetes_fp_fatigue_only_lt5pct":         fp_rate(p_hard_fat) < 0.05,
    }

    results = {
        "stage": "post_retraining",
        "date": "2026-03-30",
        "models": {
            "kidney":       "kidney_lr_v3_hard_neg",
            "inflammation": "hidden_inflammation_lr_v4_hard_neg",
            "prediabetes":  "prediabetes_xgb_v3_hard_neg (LR fallback)",
        },
        "test_set": {
            "source": "nhanes_merged_adults_final_normalized.csv 20% holdout (seed=42)",
            "kidney_n_positives": len(kidney_pos_df),
            "inflammation_n_positives": len(inflam_pos_df),
            "prediabetes_n_positives": len(predia_pos_df),
        },
        "kidney": {
            "top_1_acc": round(kidney_top1, 4),
            "top_3_acc": round(kidney_top3, 4),
            "mean_score_positives": round(float(k_pos.mean()), 4),
            "fp_rate_real_negatives_thr035": round(fp_rate(k_ctrl), 4),
            "fp_rate_fatigue_only_100_thr035": round(fp_rate(k_hard_fat), 4),
            "fp_rate_combined_200_thr035": round(fp_rate(k_hard), 4),
            "mean_score_fatigue_only": round(float(k_hard_fat.mean()), 4),
            "recall_at_thr025": round(float((k_pos >= 0.25).mean()), 4),
        },
        "hidden_inflammation": {
            "top_1_acc": round(inflam_top1, 4),
            "top_3_acc": round(inflam_top3, 4),
            "mean_score_positives": round(float(i_pos.mean()), 4),
            "fp_rate_real_negatives_thr035": round(fp_rate(i_ctrl), 4),
            "fp_rate_fatigue_only_100_thr035": round(fp_rate(i_hard_fat), 4),
            "mean_score_fatigue_only": round(float(i_hard_fat.mean()), 4),
            "intercept": round(inflam_intercept, 4) if not np.isnan(inflam_intercept) else None,
        },
        "prediabetes": {
            "top_1_acc": round(predia_top1, 4),
            "top_3_acc": round(predia_top3, 4),
            "mean_score_positives": round(float(p_pos.mean()), 4),
            "fp_rate_real_negatives_thr035": round(fp_rate(p_ctrl), 4),
            "fp_rate_fatigue_only_100_thr035": round(fp_rate(p_hard_fat), 4),
            "mean_score_fatigue_only": round(float(p_hard_fat.mean()), 4),
            "flag_rate_nhanes_holdout": round(predia_flag, 4),
            "recommended_threshold_used": PREDIA_THR,
        },
        "shared_hard_negatives_fatigue_only_100": {
            "n": len(fatigue_neg),
            "kidney_fp_rate_thr035": round(fp_rate(k_hard_fat), 4),
            "inflammation_fp_rate_thr035": round(fp_rate(i_hard_fat), 4),
            "prediabetes_fp_rate_thr035": round(fp_rate(p_hard_fat), 4),
            "passed_all_lt_5pct": bool(
                fp_rate(k_hard_fat) < 0.05 and fp_rate(i_hard_fat) < 0.05 and fp_rate(p_hard_fat) < 0.05
            ),
        },
        "shared_hard_negatives_combined_200": {
            "n": len(combined_neg),
            "note": "fatigue(100)+sleep(50)+thyroid(50); thyroid profiles may score higher due to poor-health signals",
            "kidney_fp_rate_thr035": round(fp_rate(k_hard), 4),
            "inflammation_fp_rate_thr035": round(fp_rate(i_hard), 4),
            "prediabetes_fp_rate_thr035": round(fp_rate(p_hard), 4),
        },
        "definition_of_done": dod,
        "dod_passed_count": sum(dod.values()),
        "dod_total": len(dod),
    }

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nPost-retraining results saved to: {OUTPUT_PATH}")
    print(json.dumps(results, indent=2))

    print("\n── Definition of Done ─────────────────────────────────────────────────")
    for k, v in dod.items():
        status = "✓" if v else "✗"
        print(f"  {status}  {k}")
    print(f"\n  Passed: {sum(dod.values())}/{len(dod)}")


if __name__ == "__main__":
    main()
