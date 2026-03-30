"""
capture_baseline.py
-------------------
Run existing kidney, inflammation, and prediabetes models against a
standardised synthetic test set and save results to
ml-05-retraining/eval/baseline_results.json.

The test set contains:
  - 50 true-positive profiles per condition (high signal)
  - 100 fatigue-only hard-negative controls
  - 50 sleep-only controls
  - 50 thyroid-mimic controls

Metrics captured per model:
  - top-1 accuracy (correct condition is #1 by score)
  - top-3 accuracy
  - false-positive rate on fatigue-only controls
  - mean score on controls (should be low)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODELS_DIR    = ROOT / "models_normalized"
OUTPUT_PATH   = Path(__file__).resolve().parent / "eval" / "baseline_results.json"
RNG           = np.random.default_rng(42)

# ── Load models ─────────────────────────────────────────────────────────────────

def load_model(name: str):
    path = MODELS_DIR / name
    return joblib.load(path)

KIDNEY_MODEL  = load_model("kidney_lr_deduped17_L2_v2.joblib")
KIDNEY_META   = json.loads((MODELS_DIR / "kidney_lr_deduped17_L2_v2_metadata.json").read_text())

INFLAM_MODEL  = load_model("hidden_inflammation_lr_deduped26_L2_v3.joblib")
INFLAM_META   = json.loads((MODELS_DIR / "hidden_inflammation_lr_deduped26_L2_v3_metadata.json").read_text())

PREDIA_MODEL  = load_model("prediabetes_lr_deduped34_L2_C001_v2.joblib")
PREDIA_META   = json.loads((MODELS_DIR / "prediabetes_lr_deduped34_L2_C001_v2_metadata.json").read_text())

KIDNEY_FEATS  = KIDNEY_META["features"]
INFLAM_FEATS  = INFLAM_META["features"]
PREDIA_FEATS  = PREDIA_META["features"]


# ── Synthetic profile generators ────────────────────────────────────────────────

def _rand(lo, hi, size=None):
    return RNG.uniform(lo, hi, size)

def _randint(lo, hi, size=None):
    return RNG.integers(lo, hi + 1, size=size)

def _choice(arr, size=None):
    return RNG.choice(arr, size=size)


def gen_fatigue_only(n: int = 100) -> pd.DataFrame:
    """Pure fatigue profiles — no organ-specific pathology."""
    rows = []
    for _ in range(n):
        rows.append({
            "age_years": float(_randint(25, 55)),
            "bmi": float(_rand(20, 32)),
            "waist_cm": float(_rand(70, 95)),
            "gender": float(_choice([1, 2])),
            "gender_female": float(_choice([0, 1])),
            "dpq040___feeling_tired_or_having_little_energy": float(_randint(1, 3)),
            "huq010___general_health_condition": float(_randint(2, 4)),
            "huq071___overnight_hospital_patient_in_last_year": 2.0,
            "med_count": float(_randint(0, 2)),
            "bpq020___ever_told_you_had_high_blood_pressure": 2.0,
            "bpq030___told_had_high_blood_pressure___2+_times": 2.0,
            "bpq080___doctor_told_you___high_cholesterol_level": 2.0,
            "mcq160b___ever_told_you_had_congestive_heart_failure": 2.0,
            "mcq160a___ever_told_you_had_arthritis": 2.0,
            "mcq092___ever_receive_blood_transfusion": 2.0,
            "mcq053___taking_treatment_for_anemia/past_3_mos": 2.0,
            "mcq300c___close_relative_had_diabetes": 2.0,
            "mcq010___ever_been_told_you_have_asthma": 2.0,
            "mcq195___which_type_of_arthritis_was_it?": float("nan"),
            "mcq520___abdominal_pain_during_past_12_months?": 2.0,
            "cdq010___shortness_of_breath_on_stairs/inclines": 2.0,
            "kiq005___how_often_have_urinary_leakage?": float(_randint(4, 5)),
            "kiq480___how_many_times_urinate_in_night?": float(_randint(0, 1)),
            "uacr_mg_g": float(_rand(2, 15)),
            "serum_creatinine_mg_dl": float(_rand(0.7, 1.0)),
            "LBXSUA_uric_acid_mg_dl": float(_rand(3.5, 6.0)),
            "hdl_cholesterol_mg_dl": float(_rand(45, 70)),
            "fasting_glucose_mg_dl": float(_rand(75, 99)),
            "LBXGLU_fasting_glucose_mg_dl": float(_rand(75, 99)),
            "sld012___sleep_hours___weekdays_or_workdays": float(_rand(6.5, 8.5)),
            "sld013___sleep_hours___weekends": float(_rand(7, 9)),
            "slq050___ever_told_doctor_had_trouble_sleeping?": 2.0,
            "slq030___how_often_do_you_snore?": float(_randint(1, 2)),
            "paq650___vigorous_recreational_activities": float(_randint(1, 2)),
            "paq665___moderate_recreational_activities": float(_randint(1, 2)),
            "paq620___moderate_work_activity": float(_randint(1, 2)),
            "alq130___avg_#_alcoholic_drinks/day___past_12_mos": float(_rand(0, 1)),
            "alq151___ever_have_4/5_or_more_drinks_every_day?": 2.0,
            "smq040___do_you_now_smoke_cigarettes?": 3.0,
            "smq020___smoked_at_least_100_cigarettes_in_life": 2.0,
            "smd650___avg_#_cigarettes/day_during_past_30_days": 0.0,
            "pad680___minutes_sedentary_activity": float(_rand(200, 400)),
            "ocq180___hours_worked_last_week_in_total_all_jobs": float(_rand(35, 45)),
            "huq051___#times_receive_healthcare_over_past_year": float(_randint(1, 3)),
            "kiq430___how_frequently_does_this_occur?": float("nan"),
            "kiq052___how_much_were_daily_activities_affected?": float(_randint(1, 2)),
            "mcq366d___doctor_told_to_reduce_fat_in_diet": 2.0,
            "LBDLDL_ldl_cholesterol_friedewald_mg_dl": float(_rand(80, 130)),
            "bpq050a___now_taking_prescribed_medicine_for_hbp": 2.0,
            "pregnancy_status_bin": 0.0,
            "paq605___vigorous_work_activity": float(_randint(1, 2)),
            "education_ord": float(_randint(2, 4)),
            "rhq031___had_regular_periods_in_past_12_months": float("nan"),
            "rhq060___age_at_last_menstrual_period": float("nan"),
            "rhq131___ever_been_pregnant?": float("nan"),
            "rhq160___how_many_times_have_been_pregnant?": float("nan"),
            "rhq540___ever_use_female_hormones?": float("nan"),
            "whq040___like_to_weigh_more,_less_or_same": 3.0,
            "whq070___tried_to_lose_weight_in_past_year": 2.0,
            "smq078___how_soon_after_waking_do_you_smoke": float("nan"),
            "mcq160l___ever_told_you_had_any_liver_condition": 2.0,
            "mcq160f___ever_told_you_had_stroke": 2.0,
            "mcq160e___ever_told_you_had_heart_attack": 2.0,
            "heq030___ever_told_you_have_hepatitis_c?": 2.0,
            "kiq022___ever_told_you_had_weak/failing_kidneys?": 2.0,
            "kiq026___ever_had_kidney_stones?": 2.0,
            "kiq044___urinated_before_reaching_the_toilet?": float(_randint(3, 4)),
        })
    return pd.DataFrame(rows)


def gen_sleep_only(n: int = 50) -> pd.DataFrame:
    """Sleep-disorder mimic profiles — fatigue + poor sleep, no other pathology."""
    df = gen_fatigue_only(n)
    df["sld012___sleep_hours___weekdays_or_workdays"] = _rand(4, 6, size=n)
    df["slq050___ever_told_doctor_had_trouble_sleeping?"] = 1.0
    df["slq030___how_often_do_you_snore?"] = _randint(3, 4, size=n).astype(float)
    return df


def gen_thyroid_mimic(n: int = 50) -> pd.DataFrame:
    """Thyroid mimic profiles — fatigue + weight gain + cold intolerance, but no kidney/inflam/prediabetes."""
    df = gen_fatigue_only(n)
    df["bmi"] = _rand(26, 35, size=n)
    df["waist_cm"] = _rand(80, 100, size=n)
    df["huq010___general_health_condition"] = _randint(3, 4, size=n).astype(float)
    return df


def gen_kidney_positive(n: int = 50) -> pd.DataFrame:
    """High-signal kidney profiles."""
    rows = []
    for _ in range(n):
        rows.append({
            "age_years": float(_randint(55, 80)),
            "bmi": float(_rand(26, 35)),
            "waist_cm": float(_rand(90, 115)),
            "gender": 1.0,
            "gender_female": 0.0,
            "dpq040___feeling_tired_or_having_little_energy": float(_randint(2, 3)),
            "huq010___general_health_condition": float(_randint(3, 5)),
            "huq071___overnight_hospital_patient_in_last_year": 1.0,
            "med_count": float(_randint(4, 8)),
            "bpq020___ever_told_you_had_high_blood_pressure": 1.0,
            "bpq030___told_had_high_blood_pressure___2+_times": 1.0,
            "bpq080___doctor_told_you___high_cholesterol_level": 1.0,
            "mcq160b___ever_told_you_had_congestive_heart_failure": float(_choice([1, 2])),
            "mcq160a___ever_told_you_had_arthritis": 1.0,
            "mcq092___ever_receive_blood_transfusion": float(_choice([1, 2])),
            "mcq053___taking_treatment_for_anemia/past_3_mos": float(_choice([1, 2])),
            "mcq300c___close_relative_had_diabetes": float(_choice([1, 2])),
            "mcq010___ever_been_told_you_have_asthma": 2.0,
            "mcq195___which_type_of_arthritis_was_it?": float("nan"),
            "mcq520___abdominal_pain_during_past_12_months?": float(_choice([1, 2])),
            "cdq010___shortness_of_breath_on_stairs/inclines": float(_choice([1, 2])),
            "kiq005___how_often_have_urinary_leakage?": float(_randint(1, 3)),
            "kiq480___how_many_times_urinate_in_night?": float(_randint(3, 5)),
            "uacr_mg_g": float(_rand(45, 300)),
            "serum_creatinine_mg_dl": float(_rand(1.4, 3.5)),
            "LBXSUA_uric_acid_mg_dl": float(_rand(7.0, 10.0)),
            "hdl_cholesterol_mg_dl": float(_rand(30, 50)),
            "fasting_glucose_mg_dl": float(_rand(95, 130)),
            "LBXGLU_fasting_glucose_mg_dl": float(_rand(95, 130)),
            "sld012___sleep_hours___weekdays_or_workdays": float(_rand(5, 7)),
            "sld013___sleep_hours___weekends": float(_rand(5.5, 7.5)),
            "slq050___ever_told_doctor_had_trouble_sleeping?": float(_choice([1, 2])),
            "slq030___how_often_do_you_snore?": float(_randint(2, 4)),
            "paq650___vigorous_recreational_activities": 2.0,
            "paq665___moderate_recreational_activities": float(_randint(1, 2)),
            "paq620___moderate_work_activity": float(_randint(1, 2)),
            "alq130___avg_#_alcoholic_drinks/day___past_12_mos": float(_rand(0, 1)),
            "alq151___ever_have_4/5_or_more_drinks_every_day?": 2.0,
            "smq040___do_you_now_smoke_cigarettes?": float(_choice([1, 2, 3])),
            "smq020___smoked_at_least_100_cigarettes_in_life": float(_choice([1, 2])),
            "smd650___avg_#_cigarettes/day_during_past_30_days": float(_rand(0, 15)),
            "pad680___minutes_sedentary_activity": float(_rand(400, 600)),
            "ocq180___hours_worked_last_week_in_total_all_jobs": float(_rand(20, 40)),
            "huq051___#times_receive_healthcare_over_past_year": float(_randint(5, 10)),
            "kiq430___how_frequently_does_this_occur?": float(_randint(1, 3)),
            "kiq052___how_much_were_daily_activities_affected?": float(_randint(2, 4)),
            "mcq366d___doctor_told_to_reduce_fat_in_diet": float(_choice([1, 2])),
            "LBDLDL_ldl_cholesterol_friedewald_mg_dl": float(_rand(100, 180)),
            "bpq050a___now_taking_prescribed_medicine_for_hbp": 1.0,
            "pregnancy_status_bin": 0.0,
            "paq605___vigorous_work_activity": 2.0,
            "education_ord": float(_randint(1, 3)),
            "rhq031___had_regular_periods_in_past_12_months": float("nan"),
            "rhq060___age_at_last_menstrual_period": float("nan"),
            "rhq131___ever_been_pregnant?": float("nan"),
            "rhq160___how_many_times_have_been_pregnant?": float("nan"),
            "rhq540___ever_use_female_hormones?": float("nan"),
            "whq040___like_to_weigh_more,_less_or_same": float(_choice([2, 3])),
            "whq070___tried_to_lose_weight_in_past_year": 1.0,
            "smq078___how_soon_after_waking_do_you_smoke": float("nan"),
            "mcq160l___ever_told_you_had_any_liver_condition": 2.0,
            "mcq160f___ever_told_you_had_stroke": float(_choice([1, 2])),
            "mcq160e___ever_told_you_had_heart_attack": float(_choice([1, 2])),
            "heq030___ever_told_you_have_hepatitis_c?": 2.0,
            "kiq022___ever_told_you_had_weak/failing_kidneys?": 1.0,
            "kiq026___ever_had_kidney_stones?": float(_choice([1, 2])),
            "kiq044___urinated_before_reaching_the_toilet?": float(_randint(1, 2)),
        })
    return pd.DataFrame(rows)


def gen_inflammation_positive(n: int = 50) -> pd.DataFrame:
    """High-signal inflammation profiles."""
    df = gen_fatigue_only(n)
    df["bmi"] = _rand(28, 38, size=n)
    df["waist_cm"] = _rand(95, 120, size=n)
    df["bpq030___told_had_high_blood_pressure___2+_times"] = 1.0
    df["bpq080___doctor_told_you___high_cholesterol_level"] = 1.0
    df["hdl_cholesterol_mg_dl"] = _rand(28, 42, size=n)
    df["mcq300c___close_relative_had_diabetes"] = 1.0
    df["mcq160a___ever_told_you_had_arthritis"] = 1.0
    df["mcq195___which_type_of_arthritis_was_it?"] = 3.0
    df["huq010___general_health_condition"] = _randint(3, 5, size=n).astype(float)
    df["med_count"] = _randint(3, 7, size=n).astype(float)
    df["age_years"] = _randint(45, 70, size=n).astype(float)
    return df


def gen_prediabetes_positive(n: int = 50) -> pd.DataFrame:
    """High-signal prediabetes profiles."""
    df = gen_fatigue_only(n)
    df["fasting_glucose_mg_dl"] = _rand(100, 125, size=n)
    df["LBXGLU_fasting_glucose_mg_dl"] = _rand(100, 125, size=n)
    df["bmi"] = _rand(28, 40, size=n)
    df["waist_cm"] = _rand(95, 120, size=n)
    df["mcq300c___close_relative_had_diabetes"] = 1.0
    df["age_years"] = _randint(40, 65, size=n).astype(float)
    df["bpq020___ever_told_you_had_high_blood_pressure"] = 1.0
    df["bpq080___doctor_told_you___high_cholesterol_level"] = 1.0
    df["LBDLDL_ldl_cholesterol_friedewald_mg_dl"] = _rand(130, 200, size=n)
    df["whq040___like_to_weigh_more,_less_or_same"] = 2.0
    df["mcq366d___doctor_told_to_reduce_fat_in_diet"] = 1.0
    return df


# ── Scoring helpers ─────────────────────────────────────────────────────────────

def _prepare_for_model(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    result = df.copy()
    for f in features:
        if f not in result.columns:
            result[f] = float("nan")
    return result[features]


def score_model(model, df: pd.DataFrame, features: list[str]) -> np.ndarray:
    X = _prepare_for_model(df, features)
    return model.predict_proba(X)[:, 1]


def top_k_acc(scores_dict: dict[str, np.ndarray], true_condition: str, k: int) -> float:
    """Given a dict of {condition: score_array}, compute top-k accuracy."""
    n = len(next(iter(scores_dict.values())))
    hits = 0
    for i in range(n):
        ranked = sorted(scores_dict.keys(), key=lambda c: scores_dict[c][i], reverse=True)
        if true_condition in ranked[:k]:
            hits += 1
    return hits / n


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Baseline Capture — ML-05")
    print("=" * 60)

    # Generate test sets
    fatigue_controls   = gen_fatigue_only(100)
    sleep_controls     = gen_sleep_only(50)
    thyroid_controls   = gen_thyroid_mimic(50)
    kidney_positives   = gen_kidney_positive(50)
    inflam_positives   = gen_inflammation_positive(50)
    predia_positives   = gen_prediabetes_positive(50)

    all_controls = pd.concat([fatigue_controls, sleep_controls, thyroid_controls], ignore_index=True)

    # Models to score for ranking (3-model shortlist)
    all_positives_df = pd.concat([kidney_positives, inflam_positives, predia_positives], ignore_index=True)

    # ── Kidney ──────────────────────────────────────────────────────────────────
    kidney_scores_pos    = score_model(KIDNEY_MODEL, kidney_positives, KIDNEY_FEATS)
    kidney_scores_inflam = score_model(KIDNEY_MODEL, inflam_positives, KIDNEY_FEATS)
    kidney_scores_predia = score_model(KIDNEY_MODEL, predia_positives, KIDNEY_FEATS)
    kidney_scores_ctrl   = score_model(KIDNEY_MODEL, fatigue_controls, KIDNEY_FEATS)
    kidney_scores_sleep  = score_model(KIDNEY_MODEL, sleep_controls, KIDNEY_FEATS)
    kidney_scores_thyr   = score_model(KIDNEY_MODEL, thyroid_controls, KIDNEY_FEATS)

    # ── Inflammation ─────────────────────────────────────────────────────────────
    inflam_scores_pos    = score_model(INFLAM_MODEL, inflam_positives, INFLAM_FEATS)
    inflam_scores_kidney = score_model(INFLAM_MODEL, kidney_positives, INFLAM_FEATS)
    inflam_scores_predia = score_model(INFLAM_MODEL, predia_positives, INFLAM_FEATS)
    inflam_scores_ctrl   = score_model(INFLAM_MODEL, fatigue_controls, INFLAM_FEATS)
    inflam_scores_sleep  = score_model(INFLAM_MODEL, sleep_controls, INFLAM_FEATS)
    inflam_scores_thyr   = score_model(INFLAM_MODEL, thyroid_controls, INFLAM_FEATS)

    # ── Prediabetes ──────────────────────────────────────────────────────────────
    predia_scores_pos    = score_model(PREDIA_MODEL, predia_positives, PREDIA_FEATS)
    predia_scores_kidney = score_model(PREDIA_MODEL, kidney_positives, PREDIA_FEATS)
    predia_scores_inflam = score_model(PREDIA_MODEL, inflam_positives, PREDIA_FEATS)
    predia_scores_ctrl   = score_model(PREDIA_MODEL, fatigue_controls, PREDIA_FEATS)
    predia_scores_sleep  = score_model(PREDIA_MODEL, sleep_controls, PREDIA_FEATS)
    predia_scores_thyr   = score_model(PREDIA_MODEL, thyroid_controls, PREDIA_FEATS)

    # ── Top-1 / Top-3 using 3-model shortlist ────────────────────────────────────
    THRESHOLD = 0.35

    def compute_top_k(pos_scores, comp_scores_list, k):
        """For each positive, check if its score ranks top-k among all models."""
        n = len(pos_scores)
        hits = 0
        for i in range(n):
            model_scores = [pos_scores[i]] + [s[i] for s in comp_scores_list]
            rank = sorted(model_scores, reverse=True).index(pos_scores[i]) + 1
            if rank <= k:
                hits += 1
        return hits / n

    # Kidney vs inflammation vs prediabetes
    kidney_top1 = compute_top_k(kidney_scores_pos, [inflam_scores_kidney, predia_scores_kidney], 1)
    kidney_top3 = compute_top_k(kidney_scores_pos, [inflam_scores_kidney, predia_scores_kidney], 3)

    inflam_top1 = compute_top_k(inflam_scores_pos, [kidney_scores_inflam, predia_scores_inflam], 1)
    inflam_top3 = compute_top_k(inflam_scores_pos, [kidney_scores_inflam, predia_scores_inflam], 3)

    predia_top1 = compute_top_k(predia_scores_pos, [kidney_scores_predia, inflam_scores_predia], 1)
    predia_top3 = compute_top_k(predia_scores_pos, [kidney_scores_predia, inflam_scores_predia], 3)

    # FP rate on fatigue-only controls
    def fp_rate(scores, threshold=THRESHOLD):
        return float((scores >= threshold).mean())

    # Inflammation intercept
    inflam_lr = INFLAM_MODEL.steps[-1][1]
    inflam_intercept = float(inflam_lr.intercept_[0])

    # Prediabetes flag rate on positives
    predia_flag_rate = float((predia_scores_pos >= THRESHOLD).mean())

    results = {
        "stage": "baseline",
        "date": "2026-03-30",
        "kidney": {
            "top_1_acc": round(kidney_top1, 4),
            "top_3_acc": round(kidney_top3, 4),
            "mean_score_positives": round(float(kidney_scores_pos.mean()), 4),
            "fp_rate_fatigue_controls_thr035": round(fp_rate(kidney_scores_ctrl), 4),
            "fp_rate_sleep_controls_thr035": round(fp_rate(kidney_scores_sleep), 4),
            "fp_rate_thyroid_controls_thr035": round(fp_rate(kidney_scores_thyr), 4),
            "mean_score_fatigue_controls": round(float(kidney_scores_ctrl.mean()), 4),
            "recall_at_thr025": round(float((kidney_scores_pos >= 0.25).mean()), 4),
        },
        "hidden_inflammation": {
            "top_1_acc": round(inflam_top1, 4),
            "top_3_acc": round(inflam_top3, 4),
            "mean_score_positives": round(float(inflam_scores_pos.mean()), 4),
            "fp_rate_fatigue_controls_thr035": round(fp_rate(inflam_scores_ctrl), 4),
            "fp_rate_sleep_controls_thr035": round(fp_rate(inflam_scores_sleep), 4),
            "fp_rate_thyroid_controls_thr035": round(fp_rate(inflam_scores_thyr), 4),
            "mean_score_fatigue_controls": round(float(inflam_scores_ctrl.mean()), 4),
            "intercept": round(inflam_intercept, 4),
        },
        "prediabetes": {
            "top_1_acc": round(predia_top1, 4),
            "top_3_acc": round(predia_top3, 4),
            "mean_score_positives": round(float(predia_scores_pos.mean()), 4),
            "fp_rate_fatigue_controls_thr035": round(fp_rate(predia_scores_ctrl), 4),
            "fp_rate_sleep_controls_thr035": round(fp_rate(predia_scores_sleep), 4),
            "fp_rate_thyroid_controls_thr035": round(fp_rate(predia_scores_thyr), 4),
            "mean_score_fatigue_controls": round(float(predia_scores_ctrl.mean()), 4),
            "flag_rate_positives_thr035": round(predia_flag_rate, 4),
        },
        "shared_hard_negatives": {
            "all_controls_n": len(all_controls),
            "kidney_fp_rate_all_controls": round(fp_rate(score_model(KIDNEY_MODEL, all_controls, KIDNEY_FEATS)), 4),
            "inflammation_fp_rate_all_controls": round(fp_rate(score_model(INFLAM_MODEL, all_controls, INFLAM_FEATS)), 4),
            "prediabetes_fp_rate_all_controls": round(fp_rate(score_model(PREDIA_MODEL, all_controls, PREDIA_FEATS)), 4),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nBaseline results saved to: {OUTPUT_PATH}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
