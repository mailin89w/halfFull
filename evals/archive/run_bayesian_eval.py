#!/usr/bin/env python3
"""
run_bayesian_eval.py — Synthetic cohort evaluation for the Bayesian layer.

Measures four Bayesian-specific metrics on the synthetic cohort:
  1. Posterior calibration (Brier score pre vs post Bayesian update)
  2. Coverage delta on borderline-prior cases (0.40–0.60 priors)
  3. Per-question information gain
  4. Order independence across 2–3 question permutations

Usage:
  python evals/run_bayesian_eval.py
  python evals/run_bayesian_eval.py --n 200 --seed 7
  python evals/run_bayesian_eval.py --output evals/results
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
PROFILES_PATH = EVALS_DIR / "cohort" / "profiles_v3_three_layer.json"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.quiz_to_bayesian_map import get_prefilled_answers
from bayesian.run_bayesian import handle_questions, handle_update
from evals.run_layer1_eval import _build_raw_inputs
from models_normalized.model_runner import ModelRunner
from scripts.score_answers import _patient_context, _remap_scores

LEGACY_TO_NORMALIZED = {
    "anemia": "anemia",
    "iron_deficiency": "iron_deficiency",
    "thyroid": "thyroid",
    "kidney": "kidney",
    "sleep_disorder": "sleep_disorder",
    "liver": "liver",
    "prediabetes": "prediabetes",
    "inflammation": "hidden_inflammation",
    "electrolytes": "electrolyte_imbalance",
    "hepatitis": "hepatitis_bc",
    "perimenopause": "perimenopause",
}

TARGET_TO_LEGACY = {
    "anemia": "anemia",
    "iron_deficiency": "iron_deficiency",
    "hypothyroidism": "thyroid",
    "kidney_disease": "kidney",
    "sleep_disorder": "sleep_disorder",
    "hepatitis": "hepatitis",
    "liver": "liver",
    "prediabetes": "prediabetes",
    "inflammation": "inflammation",
    "electrolyte_imbalance": "electrolytes",
    "perimenopause": "perimenopause",
    "menopause": "perimenopause",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Bayesian evals on the synthetic cohort.")
    parser.add_argument("--n", type=int, default=None, help="Optional sample size from the cohort")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed when --n is used")
    parser.add_argument("--output", type=str, default=None, help="Optional results directory override")
    parser.add_argument("--profiles-path", type=str, default=str(PROFILES_PATH), help="Path to cohort profiles JSON")
    return parser.parse_args()


def load_profiles(profiles_path: Path, n: int | None, seed: int) -> list[dict[str, Any]]:
    profiles = json.loads(profiles_path.read_text())
    if n is not None and n < len(profiles):
        rng = random.Random(seed)
        profiles = rng.sample(profiles, n)
    return profiles


def stable_random_01(*parts: str) -> float:
    raw = "::".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:12], 16) / float(16 ** 12)


def entropy_bits(prob: float) -> float:
    p = min(max(float(prob), 1e-9), 1.0 - 1e-9)
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def brier_score(predictions: list[float], labels: list[int]) -> float:
    preds = np.asarray(predictions, dtype=float)
    ys = np.asarray(labels, dtype=float)
    return float(np.mean((preds - ys) ** 2)) if len(preds) else 0.0


def reliability_bins(predictions: list[float], labels: list[int], n_bins: int = 10) -> list[dict[str, float]]:
    bins: list[dict[str, float]] = []
    if not predictions:
        return bins
    preds = np.asarray(predictions, dtype=float)
    ys = np.asarray(labels, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for idx in range(n_bins):
        lo = edges[idx]
        hi = edges[idx + 1]
        if idx == n_bins - 1:
            mask = (preds >= lo) & (preds <= hi)
        else:
            mask = (preds >= lo) & (preds < hi)
        count = int(mask.sum())
        if count == 0:
            continue
        bins.append({
            "bin_start": float(lo),
            "bin_end": float(hi),
            "count": count,
            "avg_prediction": float(preds[mask].mean()),
            "positive_rate": float(ys[mask].mean()),
        })
    return bins


def top_k(scores: dict[str, float], k: int = 5) -> list[str]:
    return [condition for condition, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]]


def map_target_to_legacy(profile: dict[str, Any]) -> str | None:
    target = profile.get("target_condition", "")
    return TARGET_TO_LEGACY.get(target)


def condition_strength(profile: dict[str, Any], legacy_condition: str) -> float:
    target = map_target_to_legacy(profile)
    if target != legacy_condition:
        return 0.0
    profile_type = profile.get("profile_type")
    if profile_type == "positive":
        return 1.0
    if profile_type == "borderline":
        return 0.65
    if profile_type == "edge":
        return 0.8
    if profile_type == "negative":
        return 0.15
    return 0.0


def duration_bucket(profile: dict[str, Any], legacy_condition: str) -> str:
    strength = condition_strength(profile, legacy_condition)
    fatigue = float(profile.get("symptom_vector", {}).get("fatigue_severity", 0.25))
    if legacy_condition == "inflammation":
        if strength >= 0.8:
            return "lt_4w"
        if strength >= 0.5:
            return "4_12w"
        if fatigue >= 0.55:
            return "12w_6m"
        return "gt_6m"
    if strength >= 0.8:
        return "gt_6m"
    if strength >= 0.5:
        return "12w_6m"
    if fatigue >= 0.45:
        return "4_12w"
    return "lt_4w"


def answer_yes(profile: dict[str, Any], qid: str, threshold: float = 0.5) -> bool:
    return stable_random_01(profile["profile_id"], qid) < threshold


def simulated_bayesian_answer(profile: dict[str, Any], condition: str, qid: str) -> str:
    demo = profile.get("demographics", {})
    sv = profile.get("symptom_vector", {})
    labs = profile.get("lab_values") or {}
    sex = demo.get("sex", "F")
    age = int(demo.get("age", 45))
    bmi = float(demo.get("bmi", 28.0))
    activity = demo.get("activity_level", "moderate")
    fatigue = float(sv.get("fatigue_severity", 0.25))
    sleep_quality = float(sv.get("sleep_quality", 0.18))
    sleep_disturbance = 1.0 - sleep_quality
    pem = float(sv.get("post_exertional_malaise", 0.17))
    joint = float(sv.get("joint_pain", 0.14))
    cognitive = float(sv.get("cognitive_impairment", 0.15))
    depressive = float(sv.get("depressive_mood", 0.15))
    anxiety = float(sv.get("anxiety_level", 0.13))
    digestive = float(sv.get("digestive_symptoms", 0.12))
    heat = float(sv.get("heat_intolerance", 0.12))
    weight_change = float(sv.get("weight_change", 0.0))
    ferritin = float(labs.get("ferritin", 60.0))
    tsh = float(labs.get("tsh", 2.0))
    hba1c = float(labs.get("hba1c", 5.3))

    anemia_strength = condition_strength(profile, "anemia")
    iron_strength = condition_strength(profile, "iron_deficiency")
    thyroid_strength = condition_strength(profile, "thyroid")
    kidney_strength = condition_strength(profile, "kidney")
    sleep_strength = condition_strength(profile, "sleep_disorder")
    hepatitis_strength = condition_strength(profile, "hepatitis")
    prediabetes_strength = condition_strength(profile, "prediabetes")
    inflammation_strength = condition_strength(profile, "inflammation")
    electrolyte_strength = condition_strength(profile, "electrolytes")
    peri_strength = condition_strength(profile, "perimenopause")

    heavy_periods = (
        sex == "F"
        and age < 53
        and (
            max(anemia_strength, iron_strength, peri_strength) >= 0.5
            or (40 <= age <= 50 and heat >= 0.55 and weight_change >= 0.1 and answer_yes(profile, qid, 0.35))
        )
    )
    unusual_blood_loss = max(anemia_strength, iron_strength) >= 0.55 or (digestive >= 0.55 and answer_yes(profile, qid, 0.25))
    blood_donation = answer_yes(profile, qid, 0.12 + (0.12 if iron_strength >= 0.5 else 0.0))
    vegetarian = answer_yes(profile, qid, 0.08 + (0.15 if iron_strength >= 0.5 else 0.0))
    nocturia = max(kidney_strength, prediabetes_strength) >= 0.4 or (sleep_disturbance >= 0.6 and fatigue >= 0.45)
    weight_loss = weight_change <= -0.2 or answer_yes(profile, qid, 0.25 if max(kidney_strength, hepatitis_strength, inflammation_strength) >= 0.5 else 0.05)
    significant_weight_gain = weight_change >= 0.2 or bmi >= 32.0
    high_alcohol = answer_yes(profile, qid, 0.55 if condition in {"liver", "hepatitis"} and hepatitis_strength >= 0.5 else 0.04)
    moderate_alcohol = high_alcohol or answer_yes(profile, qid, 0.28 if digestive >= 0.55 or electrolyte_strength >= 0.5 else 0.12)

    manual_answers = {
        "anemia_q1": "yes" if heavy_periods else "no",
        "anemia_q2": "yes" if unusual_blood_loss else "no",
        "anemia_q3": "yes" if blood_donation else "no",
        "anemia_q4": "yes" if vegetarian else "no",
        "anemia_q5": duration_bucket(profile, "anemia"),

        "iron_q1": "yes" if heavy_periods else "no",
        "iron_q2": "yes" if vegetarian else "no",
        "iron_q3": "yes" if unusual_blood_loss else "no",
        "iron_q4": "yes" if blood_donation else "no",
        "iron_q5": "yes" if (iron_strength >= 0.8 or ferritin < 20.0 or answer_yes(profile, qid, 0.08)) else "no",

        "thyroid_q1": "gained" if (thyroid_strength >= 0.5 or significant_weight_gain) else ("lost" if weight_change <= -0.2 else "no"),
        "thyroid_q2": "yes" if (thyroid_strength >= 0.4 or heat <= 0.12 or tsh >= 4.0) else "no",
        "thyroid_q3": "yes" if (thyroid_strength >= 0.65 or tsh >= 4.5 or answer_yes(profile, qid, 0.1)) else "no",
        "thyroid_q4": "yes" if (thyroid_strength >= 0.5 or digestive <= 0.08 or answer_yes(profile, qid, 0.08)) else "no",
        "thyroid_q5": duration_bucket(profile, "thyroid"),

        "kidney_q1": "yes" if (kidney_strength >= 0.8 or answer_yes(profile, qid, 0.06)) else "no",
        "kidney_q2": "yes" if (kidney_strength >= 0.55 or (bmi >= 35.0 and fatigue >= 0.7 and answer_yes(profile, qid, 0.3))) else "no",
        "kidney_q3": "yes" if nocturia else "no",
        "kidney_q4": "yes_loss" if weight_loss else "no",

        "sleep_q1": "yes" if (sleep_strength >= 0.55 or (sleep_disturbance >= 0.72 and answer_yes(profile, qid, 0.45))) else "no",
        "sleep_q2": "yes" if (sleep_disturbance >= 0.45 or bmi >= 30.0 or sleep_strength >= 0.4) else "no",
        "sleep_q3": "yes" if (sleep_strength >= 0.55 or (fatigue >= 0.68 and sleep_disturbance >= 0.45)) else "no",
        "sleep_q4": "yes" if (sleep_disturbance >= 0.4 or fatigue >= 0.6 or sleep_strength >= 0.35) else "no",
        "sleep_q5": "yes" if (sleep_disturbance >= 0.5 or anxiety >= 0.55 or sleep_strength >= 0.45) else "no",

        "liver_q1": "high_risk" if high_alcohol else ("moderate" if moderate_alcohol else ("none" if answer_yes(profile, qid, 0.35) else "low")),
        "liver_q2": "yes" if (digestive >= 0.8 and answer_yes(profile, qid, 0.18)) else "no",
        "liver_q3": "yes" if (digestive >= 0.88 and answer_yes(profile, qid, 0.12)) else "no",
        "liver_q4": "yes" if (hepatitis_strength >= 0.65 and answer_yes(profile, qid, 0.45)) else "no",
        "liver_q5": "yes" if weight_loss else "no",

        "prediabetes_q1": "yes" if (prediabetes_strength >= 0.45 or significant_weight_gain) else "no",
        "prediabetes_q2": "yes" if (prediabetes_strength >= 0.55 or hba1c >= 5.7 or (bmi >= 34.0 and fatigue >= 0.5)) else "no",
        "prediabetes_q3": "yes" if (prediabetes_strength >= 0.45 or nocturia) else "no",
        "prediabetes_q4": "none" if activity == "sedentary" else ("moderate" if activity in {"low", "moderate"} else "intensive"),

        "inflam_q1": "yes" if (inflammation_strength >= 0.45 or weight_loss) else "no",
        "inflam_q2": "yes" if (inflammation_strength >= 0.55 or (digestive >= 0.55 and answer_yes(profile, qid, 0.2))) else "no",
        "inflam_q3": "yes" if (inflammation_strength >= 0.45 or joint >= 0.45) else "no",
        "inflam_q4": duration_bucket(profile, "inflammation"),

        "elec_q1": "high_risk" if high_alcohol else ("moderate" if moderate_alcohol else "low_none"),
        "elec_q2": "yes" if (electrolyte_strength >= 0.5 or (digestive >= 0.55 and answer_yes(profile, qid, 0.4))) else "no",
        "elec_q3": "yes" if (electrolyte_strength >= 0.45 or (fatigue >= 0.62 and pem >= 0.45)) else "no",
        "elec_q4": "yes" if (electrolyte_strength >= 0.5 or (age >= 50 and answer_yes(profile, qid, 0.25))) else "no",

        "hep_q1": "high_risk" if high_alcohol else ("moderate" if moderate_alcohol else "low_none"),
        "hep_q2": "yes" if (hepatitis_strength >= 0.65 and answer_yes(profile, qid, 0.42)) else "no",
        "hep_q3": "yes" if (hepatitis_strength >= 0.45 or answer_yes(profile, qid, 0.05)) else "no",
        "hep_q4": "yes" if weight_loss else "no",

        "peri_q1": "yes" if (sex == "F" and 40 <= age <= 55 and (peri_strength >= 0.35 or heat >= 0.55 or anxiety >= 0.45)) else "no",
        "peri_q2": "yes" if (heat >= 0.55 or peri_strength >= 0.35) else "no",
        "peri_q2b": "yes" if (heat >= 0.7 and sleep_disturbance >= 0.35) else "no",
        "peri_q2c": "yes" if (sex == "F" and age >= 45 and (peri_strength >= 0.45 or answer_yes(profile, qid, 0.22))) else "no",
        "peri_q3": "yes" if (sex == "F" and 40 <= age < 55 and peri_strength >= 0.4) else "no",
        "peri_q4": "yes" if heavy_periods else "no",
        "peri_q5": "yes" if (peri_strength >= 0.35 and (depressive + anxiety + cognitive) / 3.0 >= 0.45) else "no",
    }
    return manual_answers[qid]


def build_prefilled_by_condition(updater: BayesianUpdater, raw_inputs: dict[str, Any], patient_sex: str | None) -> dict[str, dict[str, str]]:
    prefilled = get_prefilled_answers(raw_inputs)
    q_to_condition: dict[str, str] = {}
    for condition in updater._conditions:
        for question in updater.get_questions(condition, prior_prob=0.5, patient_sex=patient_sex, max_questions=50):
            q_to_condition[question["id"]] = condition
    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for qid, answer in prefilled.items():
        condition = q_to_condition.get(qid)
        if condition:
            grouped[condition][qid] = answer
    return grouped


def score_ml_profile(runner: ModelRunner, profile: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    raw_inputs = _build_raw_inputs(profile)
    feature_vectors = runner._get_normalizer().build_feature_vectors(raw_inputs)
    raw_scores = runner.run_all_with_context(feature_vectors, patient_context=_patient_context(raw_inputs))
    legacy_scores = _remap_scores(raw_scores)
    return legacy_scores, raw_inputs


def collect_profile_result(updater: BayesianUpdater, runner: ModelRunner, profile: dict[str, Any]) -> dict[str, Any]:
    ml_scores, raw_inputs = score_ml_profile(runner, profile)
    patient_sex = "female" if raw_inputs.get("gender") == 2 else "male" if raw_inputs.get("gender") == 1 else None
    questions_payload = {
        "ml_scores": ml_scores,
        "patient_sex": patient_sex,
        "existing_answers": raw_inputs,
    }
    questions_result = handle_questions(questions_payload, updater)
    condition_groups = questions_result.get("condition_questions", [])

    answers_by_condition: dict[str, dict[str, str]] = {}
    for group in condition_groups:
        condition = group["condition"]
        for question in group.get("questions", []):
            qid = question["id"]
            answers_by_condition.setdefault(condition, {})[qid] = simulated_bayesian_answer(profile, condition, qid)

    update_payload = {
        "ml_scores": ml_scores,
        "confounder_answers": {},
        "answers_by_condition": answers_by_condition,
        "patient_sex": patient_sex,
        "existing_answers": raw_inputs,
    }
    update_result = handle_update(update_payload, updater)

    prefilled_by_condition = build_prefilled_by_condition(updater, raw_inputs, patient_sex)
    mapped_target = map_target_to_legacy(profile)
    return {
        "profile_id": profile["profile_id"],
        "profile_type": profile.get("profile_type"),
        "target_condition": profile.get("target_condition"),
        "mapped_target_condition": mapped_target,
        "ml_scores": ml_scores,
        "posterior_scores": update_result["posterior_scores"],
        "details": update_result["details"],
        "condition_questions": condition_groups,
        "answers_by_condition": answers_by_condition,
        "prefilled_by_condition": prefilled_by_condition,
    }


def compute_calibration(profile_results: list[dict[str, Any]]) -> dict[str, Any]:
    pre_predictions: list[float] = []
    post_predictions: list[float] = []
    labels: list[int] = []
    triggered_pre: list[float] = []
    triggered_post: list[float] = []
    triggered_labels: list[int] = []

    all_conditions = list(LEGACY_TO_NORMALIZED.keys())
    for result in profile_results:
        target = result["mapped_target_condition"]
        asked_conditions = {item["condition"] for item in result["condition_questions"]}
        for condition in all_conditions:
            label = 1 if target == condition else 0
            prior = float(result["ml_scores"].get(condition, 0.0))
            posterior = float(result["posterior_scores"].get(condition, prior))
            pre_predictions.append(prior)
            post_predictions.append(posterior)
            labels.append(label)
            if condition in asked_conditions:
                triggered_pre.append(prior)
                triggered_post.append(posterior)
                triggered_labels.append(label)

    pre_brier = brier_score(pre_predictions, labels)
    post_brier = brier_score(post_predictions, labels)
    triggered_pre_brier = brier_score(triggered_pre, triggered_labels)
    triggered_post_brier = brier_score(triggered_post, triggered_labels)
    return {
        "pre_brier": pre_brier,
        "post_brier": post_brier,
        "delta": post_brier - pre_brier,
        "pass": post_brier <= pre_brier,
        "triggered_pre_brier": triggered_pre_brier,
        "triggered_post_brier": triggered_post_brier,
        "triggered_delta": triggered_post_brier - triggered_pre_brier,
        "reliability_pre": reliability_bins(pre_predictions, labels),
        "reliability_post": reliability_bins(post_predictions, labels),
    }


def compute_coverage_delta(profile_results: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        result for result in profile_results
        if result["mapped_target_condition"] is not None
        and any(0.40 <= float(prob) <= 0.60 for prob in result["ml_scores"].values())
        and len(result["condition_questions"]) > 0
    ]
    if not eligible:
        return {"n_profiles": 0, "pre_top5_coverage": 0.0, "post_top5_coverage": 0.0, "delta": 0.0, "pass": False}

    pre_hits = sum(1 for result in eligible if result["mapped_target_condition"] in top_k(result["ml_scores"], 5))
    post_hits = sum(1 for result in eligible if result["mapped_target_condition"] in top_k(result["posterior_scores"], 5))
    pre_cov = pre_hits / len(eligible)
    post_cov = post_hits / len(eligible)
    delta = post_cov - pre_cov
    return {
        "n_profiles": len(eligible),
        "pre_top5_coverage": pre_cov,
        "post_top5_coverage": post_cov,
        "delta": delta,
        "pass": delta >= 0.02,
    }


def compute_question_information_gain(updater: BayesianUpdater, profile_results: list[dict[str, Any]]) -> dict[str, Any]:
    per_question: dict[str, dict[str, Any]] = defaultdict(lambda: {"condition": None, "gains": []})
    for result in profile_results:
        for group in result["condition_questions"]:
            condition = group["condition"]
            prior = float(result["ml_scores"].get(condition, 0.0))
            prefilled_answers = dict(result["prefilled_by_condition"].get(condition, {}))
            base_posterior = updater.update(
                LEGACY_TO_NORMALIZED[condition],
                prior_prob=prior,
                answers=prefilled_answers,
                confounder_multiplier=1.0,
            )["posterior"]
            for question in group.get("questions", []):
                qid = question["id"]
                answer = result["answers_by_condition"].get(condition, {}).get(qid)
                if answer is None:
                    continue
                answers = {**prefilled_answers, qid: answer}
                posterior = updater.update(
                    LEGACY_TO_NORMALIZED[condition],
                    prior_prob=prior,
                    answers=answers,
                    confounder_multiplier=1.0,
                )["posterior"]
                gain = entropy_bits(base_posterior) - entropy_bits(posterior)
                per_question[qid]["condition"] = condition
                per_question[qid]["text"] = question["text"]
                per_question[qid]["gains"].append(float(gain))

    ranked: list[dict[str, Any]] = []
    for qid, stats in per_question.items():
        gains = stats["gains"]
        avg_gain = float(np.mean(gains)) if gains else 0.0
        ranked.append({
            "question_id": qid,
            "condition": stats["condition"],
            "text": stats["text"],
            "n_asked": len(gains),
            "avg_information_gain_bits": avg_gain,
            "candidate_for_removal": avg_gain < 0.02,
        })
    ranked.sort(key=lambda item: item["avg_information_gain_bits"])
    return {
        "questions": ranked,
        "candidates_for_removal": [item for item in ranked if item["candidate_for_removal"]],
    }


def compute_order_independence(updater: BayesianUpdater, profile_results: list[dict[str, Any]], sample_size: int = 50) -> dict[str, Any]:
    candidates: list[tuple[dict[str, Any], str, list[str]]] = []
    for result in profile_results:
        for group in result["condition_questions"]:
            qids = list(result["answers_by_condition"].get(group["condition"], {}).keys())
            if len(qids) >= 2:
                candidates.append((result, group["condition"], qids[: min(3, len(qids))]))

    if not candidates:
        return {"n_samples": 0, "mean_variance": 0.0, "max_variance": 0.0, "pass": False, "samples": []}

    selected = candidates[:sample_size]
    samples: list[dict[str, Any]] = []
    variances: list[float] = []
    for result, condition, qids in selected:
        prior = float(result["ml_scores"].get(condition, 0.0))
        prefilled_answers = dict(result["prefilled_by_condition"].get(condition, {}))
        asked_answers = result["answers_by_condition"][condition]
        permutations = list(itertools.permutations(qids))
        posteriors: list[float] = []
        for ordering in permutations:
            ordered_answers = dict(prefilled_answers)
            for qid in ordering:
                ordered_answers[qid] = asked_answers[qid]
            posterior = updater.update(
                LEGACY_TO_NORMALIZED[condition],
                prior_prob=prior,
                answers=ordered_answers,
                confounder_multiplier=1.0,
            )["posterior"]
            posteriors.append(float(posterior))
        variance = float(np.var(posteriors))
        variances.append(variance)
        samples.append({
            "profile_id": result["profile_id"],
            "condition": condition,
            "question_ids": qids,
            "posterior_min": float(min(posteriors)),
            "posterior_max": float(max(posteriors)),
            "variance": variance,
        })

    samples.sort(key=lambda item: item["variance"], reverse=True)
    mean_variance = float(np.mean(variances)) if variances else 0.0
    max_variance = float(max(variances)) if variances else 0.0
    return {
        "n_samples": len(samples),
        "mean_variance": mean_variance,
        "max_variance": max_variance,
        "pass": max_variance < 0.02,
        "samples": samples[:10],
    }


def to_markdown(report: dict[str, Any]) -> str:
    calibration = report["posterior_calibration"]
    coverage = report["coverage_delta_post_bayesian"]
    info_gain = report["question_information_gain"]
    order = report["order_independence"]

    lines = [
        f"# Bayesian Eval Report — {report['run_id']}",
        "",
        "## Summary",
        "",
        f"| Metric | Target | Actual | Status |",
        "|---|---:|---:|---|",
        f"| Posterior calibration | post Brier <= pre Brier | {calibration['post_brier']:.4f} vs {calibration['pre_brier']:.4f} | {'PASS' if calibration['pass'] else 'FAIL'} |",
        f"| Coverage delta | >= +2.0 pp | {coverage['delta'] * 100:.2f} pp | {'PASS' if coverage['pass'] else 'FAIL'} |",
        f"| Low-gain questions flagged | < 0.02 bits | {len(info_gain['candidates_for_removal'])} flagged | INFO |",
        f"| Order independence | variance < 0.02 | max {order['max_variance']:.6f} | {'PASS' if order['pass'] else 'FAIL'} |",
        "",
        "## Posterior Calibration",
        "",
        f"- Profiles evaluated: {report['n_profiles']}",
        f"- Overall pre-update Brier: {calibration['pre_brier']:.4f}",
        f"- Overall post-update Brier: {calibration['post_brier']:.4f}",
        f"- Delta: {calibration['delta']:+.4f}",
        f"- Triggered-only delta: {calibration['triggered_delta']:+.4f}",
        "",
        "## Coverage Delta",
        "",
        f"- Eligible profiles: {coverage['n_profiles']}",
        f"- Pre-update top-5 coverage: {coverage['pre_top5_coverage']:.1%}",
        f"- Post-update top-5 coverage: {coverage['post_top5_coverage']:.1%}",
        f"- Delta: {coverage['delta'] * 100:.2f} percentage points",
        "",
        "## Low-Gain Question Candidates",
        "",
        "| Question | Condition | N Asked | Avg gain (bits) |",
        "|---|---|---:|---:|",
    ]
    for item in info_gain["questions"][:10]:
        lines.append(
            f"| {item['question_id']} | {item['condition']} | {item['n_asked']} | {item['avg_information_gain_bits']:.4f} |"
        )
    lines.extend([
        "",
        "## Order Independence",
        "",
        f"- Samples tested: {order['n_samples']}",
        f"- Mean posterior variance across permutations: {order['mean_variance']:.6f}",
        f"- Max posterior variance across permutations: {order['max_variance']:.6f}",
    ])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output) if args.output else RESULTS_DIR
    profiles_path = Path(args.profiles_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles(profiles_path, args.n, args.seed)
    runner = ModelRunner()
    updater = BayesianUpdater()

    profile_results = [collect_profile_result(updater, runner, profile) for profile in profiles]
    calibration = compute_calibration(profile_results)
    coverage = compute_coverage_delta(profile_results)
    info_gain = compute_question_information_gain(updater, profile_results)
    order = compute_order_independence(updater, profile_results)

    run_id = datetime.utcnow().strftime("bayesian_%Y%m%d_%H%M%S")
    report = {
        "run_id": run_id,
        "n_profiles": len(profile_results),
        "profiles_path": str(profiles_path),
        "posterior_calibration": calibration,
        "coverage_delta_post_bayesian": coverage,
        "question_information_gain": info_gain,
        "order_independence": order,
        "profile_results": profile_results,
    }

    json_path = output_dir / f"{run_id}.json"
    md_path = REPORTS_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(to_markdown(report))

    print(f"Saved JSON report to {json_path}")
    print(f"Saved Markdown report to {md_path}")
    print(f"Posterior calibration delta: {calibration['delta']:+.4f}")
    print(f"Coverage delta: {coverage['delta'] * 100:+.2f} pp")
    print(f"Low-gain questions: {len(info_gain['candidates_for_removal'])}")
    print(f"Order independence max variance: {order['max_variance']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
