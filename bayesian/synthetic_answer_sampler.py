from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


_DIR = Path(__file__).resolve().parent
_SPECS_PATH = _DIR / "synthetic_question_specs.json"
QUESTION_SPECS = json.loads(_SPECS_PATH.read_text(encoding="utf-8"))["questions"]


def _num(value: Any) -> float | None:
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(value) else float(value)


def _flag(value: Any) -> int:
    if pd.isna(value):
        return 0
    return int(float(value))


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _stable_unit(seed_key: str) -> float:
    import hashlib

    digest = hashlib.sha256(seed_key.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16**12 - 1)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _scaled_probability(signal: float, midpoint: float, slope: float = 8.0) -> float:
    return _clip01(_sigmoid((signal - midpoint) * slope))


def _sample_binary(seqn: int, qid: str, signal: float, yes_mid: float, base_yes: float, base_no: float) -> str:
    prob_yes = base_yes + (base_no - base_yes) * _scaled_probability(signal, yes_mid)
    draw = _stable_unit(f"{seqn}:{qid}:binary")
    return "yes" if draw < prob_yes else "no"


def _sample_duration(seqn: int, qid: str, chronicity: float) -> str:
    chronicity = _clip01(chronicity + (_stable_unit(f"{seqn}:{qid}:dur_jitter") - 0.5) * 0.12)
    if chronicity >= 0.82:
        return "gt_6m"
    if chronicity >= 0.58:
        return "12w_6m"
    if chronicity >= 0.34:
        return "4_12w"
    return "lt_4w"


def _sample_alcohol_general(avg_drinks_day: float | None) -> str:
    if avg_drinks_day is None or avg_drinks_day <= 0:
        return "low_none"
    if avg_drinks_day >= 4:
        return "high_risk"
    if avg_drinks_day >= 2:
        return "moderate"
    return "low_none"


def _sample_alcohol_liver(avg_drinks_day: float | None) -> str:
    if avg_drinks_day is None or avg_drinks_day <= 0:
        return "none"
    if avg_drinks_day >= 4:
        return "high_risk"
    if avg_drinks_day >= 2:
        return "moderate"
    return "low"


def _derive_latent_states(row: pd.Series, symptom_vector: dict[str, float]) -> dict[str, float]:
    age = _num(row.get("age_years")) or 45.0
    female = str(row.get("gender")) == "Female"
    bmi = _num(row.get("bmi")) or 27.0
    ferritin = _num(row.get("ferritin_ng_ml"))
    hgb = _num(row.get("hemoglobin_g_dl"))
    hba1c = _num(row.get("hba1c_pct"))
    crp = _num(row.get("crp_mg_l"))
    creat = _num(row.get("serum_creatinine_mg_dl"))
    sodium = _num(row.get("sodium_mmol_l"))
    potassium = _num(row.get("potassium_mmol_l"))
    calcium = _num(row.get("calcium_mg_dl"))
    alt = _num(row.get("alt_u_l"))
    ast = _num(row.get("ast_u_l"))
    ggt = _num(row.get("ggt_u_l"))
    wbc = _num(row.get("wbc_1000_cells_ul"))
    alcohol = _num(row.get("alq130_avg_drinks_per_day"))
    nocturia = _num(row.get("kiq480_nocturia"))
    snore = _num(row.get("slq030_snore_freq"))
    stop_breathing = _num(row.get("slq040_stop_breathing_freq"))
    sleep_problem = _num(row.get("slq050_sleep_trouble_doctor"))
    transfusion = _num(row.get("mcq092_transfusion"))
    arthritis = _num(row.get("mcq160a_arthritis"))
    regular_periods = _num(row.get("rhq031_regular_periods"))
    fatigue = float(symptom_vector.get("fatigue_severity", 0.2))
    sleep_quality = float(symptom_vector.get("sleep_quality", 0.7))
    joint_pain = float(symptom_vector.get("joint_pain", 0.12))
    digestive = float(symptom_vector.get("digestive_symptoms", 0.1))
    heat = float(symptom_vector.get("heat_intolerance", 0.1))
    depressive = float(symptom_vector.get("depressive_mood", 0.12))
    anxiety = float(symptom_vector.get("anxiety_level", 0.12))
    weight_change = float(symptom_vector.get("weight_change", 0.0))

    anemia = _flag(row.get("anemia"))
    iron = _flag(row.get("iron_deficiency"))
    thyroid = _flag(row.get("thyroid"))
    kidney = _flag(row.get("kidney"))
    sleep = _flag(row.get("sleep_disorder"))
    liver = _flag(row.get("liver"))
    hepatitis = _flag(row.get("hepatitis_bc"))
    inflammation = _flag(row.get("hidden_inflammation"))
    electrolytes = _flag(row.get("electrolyte_imbalance"))
    peri = _flag(row.get("perimenopause_proxy_probable"))

    heavy_period_context = 1.0 if female and age < 53 and (anemia or iron or peri) else 0.0
    blood_loss_burden = _clip01(0.6 * heavy_period_context + 0.35 * (_flag(transfusion == 1)) + 0.15 * max(-weight_change, 0.0))
    bleeding_burden = _clip01(0.7 * heavy_period_context + 0.3 * blood_loss_burden)
    low_iron_intake = 0.25 if iron or anemia else 0.07
    donation_exposure = 0.22 if iron else 0.08
    pica_proxy = _clip01((0.75 if ferritin is not None and ferritin < 20 else 0.15) + (0.2 if iron else 0.0))

    thyroid_cold_pattern = _clip01((0.7 if thyroid else 0.1) + (0.25 if heat < 0.25 else 0.0))
    thyroid_dryskin_pattern = _clip01((0.6 if thyroid else 0.08) + 0.15 * fatigue)
    thyroid_constipation_pattern = _clip01((0.55 if thyroid else 0.08) + (0.2 if digestive < 0.2 else 0.0))
    thyroid_duration = _clip01(0.75 * thyroid + 0.25 * fatigue)
    if weight_change >= 0.18 or bmi >= 32 or thyroid:
        thyroid_weight_pattern = 0.85
    elif weight_change <= -0.18:
        thyroid_weight_pattern = 0.18
    else:
        thyroid_weight_pattern = 0.5

    known_kidney_history = _clip01(0.82 * kidney)
    kidney_bp_or_diabetes_context = _clip01(0.55 * kidney + 0.15 * (bmi >= 35) + 0.15 * ((_num(row.get("bpq020_high_bp")) or 2) == 1) + 0.15 * ((_num(row.get("diq010_diabetes")) or 2) == 1))
    nocturia_burden = _clip01((0.65 if nocturia is not None and nocturia >= 2 else 0.1) + 0.2 * kidney + 0.15 * (_flag((hba1c or 0) >= 5.7)))
    weight_loss_flag = _clip01(0.85 if weight_change <= -0.2 else 0.05)

    sleep_fragmentation = _clip01((1.0 - sleep_quality) * 0.7 + (0.2 if sleep else 0.0))
    apnea_signal = _clip01((0.55 if stop_breathing is not None and stop_breathing >= 2 else 0.08) + 0.2 * sleep_fragmentation + 0.12 * (bmi >= 30))
    snoring_signal = _clip01((0.55 if snore is not None and snore >= 2 else 0.1) + 0.15 * (bmi >= 30))
    sleep_daytime_sleepiness = _clip01(0.55 * sleep_fragmentation + 0.35 * fatigue + 0.15 * sleep)
    insomnia_pattern = _clip01((0.6 if sleep_problem == 1 else 0.1) + 0.25 * sleep_fragmentation + 0.15 * max(anxiety, depressive))

    hepatic_enzyme_signal = _clip01(
        (0.28 if alt is not None and alt >= 40 else 0.0)
        + (0.22 if ast is not None and ast >= 40 else 0.0)
        + (0.25 if ggt is not None and ggt >= 60 else 0.0)
    )
    hepatic_burden = _clip01(0.45 * liver + 0.35 * hepatitis + 0.25 * digestive + hepatic_enzyme_signal)
    catabolic_weight_loss = _clip01((0.65 if weight_change <= -0.25 else 0.05) + 0.15 * hepatic_burden + 0.15 * inflammation)
    jaundice_proxy = _clip01(0.45 * hepatitis + 0.35 * liver + 0.18 * hepatic_enzyme_signal)
    spider_angioma_proxy = _clip01(0.45 * liver + 0.15 * hepatic_enzyme_signal + 0.10 * ((_num(alcohol) or 0.0) >= 4))
    ascites_proxy = _clip01(0.38 * liver + 0.24 * digestive + 0.18 * catabolic_weight_loss)

    glycemic_signal = _clip01((0.55 if hba1c is not None and hba1c >= 5.7 else 0.05) + 0.20 * (bmi >= 32) + 0.15 * (_flag((_num(row.get("diq160_prediabetes")) or 2) == 1)))
    weight_gain_burden = _clip01((0.65 if weight_change >= 0.2 else 0.08) + 0.15 * (bmi >= 32))
    activity_pattern = 0.1 if str(row.get("activity_level")) == "sedentary" else 0.55 if str(row.get("activity_level")) in {"low", "moderate"} else 0.9

    chronic_inflammation_duration = _clip01(0.75 * inflammation + 0.2 * fatigue)
    acute_infection_recent = _clip01((0.75 if (wbc is not None and wbc > 11) or (crp is not None and crp > 10) else 0.08) + 0.15 * digestive)
    joint_inflammation_pattern = _clip01((0.55 if arthritis == 1 else 0.08) + 0.35 * joint_pain + 0.15 * inflammation)

    electrolyte_shift = _clip01(
        (0.28 if sodium is not None and (sodium < 136 or sodium > 145) else 0.0)
        + (0.28 if potassium is not None and (potassium < 3.5 or potassium > 5.0) else 0.0)
        + (0.22 if calcium is not None and (calcium < 8.5 or calcium > 10.5) else 0.0)
    )
    gi_loss_recent = _clip01(0.3 * digestive + 0.35 * catabolic_weight_loss + 0.15 * electrolytes)
    muscle_irritability_pattern = _clip01(0.45 * electrolytes + 0.22 * fatigue + 0.18 * float(symptom_vector.get("post_exertional_malaise", 0.1)))
    electrolyte_medication_exposure = _clip01(
        0.18 * (((_num(row.get("med_count")) or 0) >= 4))
        + 0.25 * (((_num(alcohol) or 0.0) >= 4))
        + 0.18 * (age >= 50)
        + 0.22 * electrolytes
    )

    hepatitis_exposure_risk = _clip01(0.45 * (_flag(transfusion == 1)) + 0.25 * hepatitis + 0.08 * ((_num(alcohol) or 0.0) >= 4))

    menstrual_irregularity = _clip01((0.7 if female and 40 <= age < 55 and regular_periods == 2 else 0.04) + 0.15 * peri)
    vasomotor_burden = _clip01(0.65 * heat + 0.22 * peri)
    night_sweat_burden = _clip01(0.55 * heat + 0.25 * (1.0 - sleep_quality) + 0.18 * peri)
    age_transition_context = _clip01(0.7 if female and age >= 45 else 0.1)
    perimenopause_self_assessment = _clip01(0.45 * peri + 0.25 * vasomotor_burden + 0.15 * menstrual_irregularity)
    perimenopause_mood_burden = _clip01(0.25 * peri + 0.35 * max(depressive, anxiety) + 0.15 * (1.0 - sleep_quality))

    alcohol_risk_general = _clip01((min((alcohol or 0.0) / 4.0, 1.0)) if alcohol is not None else 0.0)
    alcohol_risk_hepatitis = _clip01(min((alcohol or 0.0) / 5.0, 1.0) if alcohol is not None else 0.0)
    alcohol_risk_liver = _clip01(min((alcohol or 0.0) / 5.0, 1.0) if alcohol is not None else 0.0)

    anemia_fatigue_duration = _clip01(max(0.7 * max(anemia, iron), 0.35 * fatigue))

    return {
        "bleeding_burden": bleeding_burden,
        "blood_loss_burden": blood_loss_burden,
        "donation_exposure": donation_exposure,
        "low_iron_intake": low_iron_intake,
        "pica_proxy": pica_proxy,
        "anemia_fatigue_duration": anemia_fatigue_duration,
        "thyroid_weight_pattern": thyroid_weight_pattern,
        "thyroid_cold_pattern": thyroid_cold_pattern,
        "thyroid_dryskin_pattern": thyroid_dryskin_pattern,
        "thyroid_constipation_pattern": thyroid_constipation_pattern,
        "thyroid_duration": thyroid_duration,
        "known_kidney_history": known_kidney_history,
        "kidney_bp_or_diabetes_context": kidney_bp_or_diabetes_context,
        "nocturia_burden": nocturia_burden,
        "weight_loss_flag": weight_loss_flag,
        "apnea_signal": apnea_signal,
        "snoring_signal": snoring_signal,
        "sleep_daytime_sleepiness": sleep_daytime_sleepiness,
        "sleep_fragmentation": sleep_fragmentation,
        "insomnia_pattern": insomnia_pattern,
        "alcohol_risk_general": alcohol_risk_general,
        "alcohol_risk_hepatitis": alcohol_risk_hepatitis,
        "alcohol_risk_liver": alcohol_risk_liver,
        "spider_angioma_proxy": spider_angioma_proxy,
        "ascites_proxy": ascites_proxy,
        "jaundice_proxy": jaundice_proxy,
        "catabolic_weight_loss": catabolic_weight_loss,
        "glycemic_signal": glycemic_signal,
        "weight_gain_burden": weight_gain_burden,
        "activity_pattern": activity_pattern,
        "acute_infection_recent": acute_infection_recent,
        "joint_inflammation_pattern": joint_inflammation_pattern,
        "chronic_inflammation_duration": chronic_inflammation_duration,
        "gi_loss_recent": gi_loss_recent,
        "muscle_irritability_pattern": muscle_irritability_pattern,
        "electrolyte_medication_exposure": electrolyte_medication_exposure,
        "hepatitis_exposure_risk": hepatitis_exposure_risk,
        "menstrual_irregularity": menstrual_irregularity,
        "vasomotor_burden": vasomotor_burden,
        "night_sweat_burden": night_sweat_burden,
        "age_transition_context": age_transition_context,
        "perimenopause_self_assessment": perimenopause_self_assessment,
        "perimenopause_mood_burden": perimenopause_mood_burden,
    }


def generate_bayesian_answers(row: pd.Series, symptom_vector: dict[str, float]) -> dict[str, str]:
    seqn = int(row["SEQN"])
    states = _derive_latent_states(row, symptom_vector)
    alcohol = _num(row.get("alq130_avg_drinks_per_day"))
    weight_change = float(symptom_vector.get("weight_change", 0.0))
    answers: dict[str, str] = {}

    for qid, spec in QUESTION_SPECS.items():
        kind = spec["kind"]
        state_name = spec["state"]
        signal = float(states.get(state_name, 0.0))
        if kind == "binary":
            answers[qid] = _sample_binary(
                seqn=seqn,
                qid=qid,
                signal=signal,
                yes_mid=float(spec["yes_mid"]),
                base_yes=float(spec["base_yes"]),
                base_no=float(spec["base_no"]),
            )
        elif kind == "duration":
            answers[qid] = _sample_duration(seqn, qid, signal)
        elif kind == "categorical":
            if qid in {"hep_q1", "elec_q1"}:
                answers[qid] = _sample_alcohol_general(alcohol)
            elif qid == "liver_q1":
                answers[qid] = _sample_alcohol_liver(alcohol)
            elif qid == "thyroid_q1":
                if signal >= 0.7:
                    answers[qid] = "gained"
                elif signal <= 0.3 or weight_change <= -0.2:
                    answers[qid] = "lost"
                else:
                    answers[qid] = "no"
            elif qid == "kidney_q4":
                answers[qid] = "yes_loss" if signal >= 0.5 else "no"
            elif qid == "prediabetes_q4":
                if signal <= 0.2:
                    answers[qid] = "none"
                elif signal >= 0.8:
                    answers[qid] = "intensive"
                else:
                    answers[qid] = "moderate"
    return answers
