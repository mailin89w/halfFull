"""
audit_inflammation_missed.py
-----------------------------
ML-INFLAM-02 — Step 2 (contingency): Missed-Positive Audit

Run this script if validate_inflammation_v4.py concludes that v4 recall
is still below 15% ("still dead"). This audit tries to answer:

  1. What do the missed inflammation positives look like?
  2. Do they look like "generic illness" rather than true inflammation?
  3. Is the `hidden_inflammation` label too fuzzy for our current feature set?

Method:
  - Load the 760-cohort inflammation positives (55 profiles).
  - Score them with v3 and v4. Classify each as:
      found_by_v4   — v4 catches it (TP)
      found_by_v3   — only v3 catches it
      missed_both   — neither model catches it
  - Compare feature distributions across those three groups.
  - Check for overlap with conditions that look like "generic illness"
    (poor general health, fatigue, high BMI, many comorbidities).
  - Output a plain-English label-fuzziness assessment.

Outputs:
  results/inflammation_missed_audit.json
  results/inflammation_missed_audit.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

import logging
import warnings
import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_MODELS_DIR = _ROOT / "models_normalized"
sys.path.insert(0, str(_MODELS_DIR))

COHORT_PATH = _ROOT / "evals" / "cohort" / "nhanes_balanced_760.json"
RESULTS_DIR = _HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

V3_PATH = _MODELS_DIR / "hidden_inflammation_lr_deduped26_L2_v3.joblib"
V4_PATH = _MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg.joblib"

THRESHOLD_V3 = 0.40
THRESHOLD_V4 = 0.40

# Features that most strongly separate "generic illness" from true inflammation.
# "Generic illness" signals: poor health self-report, high med burden, fatigue, comorbidities.
# "True inflammation" signals: arthritis type, waist, HDL, BP, specific markers.
GENERIC_ILLNESS_FEATURES = [
    "huq010___general_health_condition",      # self-reported poor health
    "med_count",                               # many medications
    "huq051___#times_receive_healthcare_over_past_year",  # frequent healthcare
    "cdq010___shortness_of_breath_on_stairs/inclines",    # fatigue/dyspnoea
    "sld012___sleep_hours___weekdays_or_workdays",        # poor sleep
    "bpq030___told_had_high_blood_pressure___2+_times",   # chronic comorbidity
    "mcq053___taking_treatment_for_anemia/past_3_mos",    # anemia overlap
]

TRUE_INFLAMMATION_FEATURES = [
    "waist_cm",                                # central adiposity
    "waist_elevated_female",                   # sex-specific waist flag
    "waist_elevated_male",
    "hdl_cholesterol_mg_dl",                  # low HDL = metabolic syndrome
    "bpq080___doctor_told_you___high_cholesterol_level",  # dyslipidaemia
    "mcq195___which_type_of_arthritis_was_it?",           # rheumatoid vs OA
    "alq130___avg_#_alcoholic_drinks/day___past_12_mos",  # alcohol intake
]

V4_FEATURES = [
    "age_years", "hdl_cholesterol_mg_dl", "huq010___general_health_condition",
    "med_count", "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "sld012___sleep_hours___weekdays_or_workdays", "paq650___vigorous_recreational_activities",
    "rhq031___had_regular_periods_in_past_12_months", "slq030___how_often_do_you_snore?",
    "bpq080___doctor_told_you___high_cholesterol_level",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "mcq053___taking_treatment_for_anemia/past_3_mos",
    "smd650___avg_#_cigarettes/day_during_past_30_days",
    "bpq030___told_had_high_blood_pressure___2+_times",
    "huq051___#times_receive_healthcare_over_past_year",
    "kiq430___how_frequently_does_this_occur?",
    "mcq195___which_type_of_arthritis_was_it?",
    "mcq300c___close_relative_had_diabetes",
    "ocq180___hours_worked_last_week_in_total_all_jobs",
    "pregnancy_status_bin", "rhq131___ever_been_pregnant?",
    "rhq160___how_many_times_have_been_pregnant?",
    "smq020___smoked_at_least_100_cigarettes_in_life",
    "smq040___do_you_now_smoke_cigarettes?",
    "waist_cm", "waist_elevated_female", "waist_elevated_male",
]


def load_cohort(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("profiles", [])


def get_expected_conditions(profile: dict) -> list[str]:
    """Read condition_ids from ground_truth (canonical location in 760-cohort)."""
    gt = profile.get("ground_truth", {})
    return [c["condition_id"] for c in gt.get("expected_conditions", [])]


def _gender_female_from_raw(raw: dict) -> float:
    g = raw.get("gender")
    if g is None:
        return float("nan")
    if isinstance(g, str):
        return 1.0 if g.strip().lower() == "female" else 0.0
    code = int(g)
    return 1.0 if code == 2 else (0.0 if code == 1 else float("nan"))


def derive_waist_flags(normalized_row: dict, raw: dict) -> dict:
    """Add waist elevation flags using the z-scored waist_cm from the normalizer."""
    result = dict(normalized_row)
    waist_norm = float(result.get("waist_cm", float("nan")) or float("nan"))
    g_female   = _gender_female_from_raw(raw)

    if np.isnan(g_female) or np.isnan(waist_norm):
        result["waist_elevated_female"] = float("nan")
        result["waist_elevated_male"]   = float("nan")
    else:
        result["waist_elevated_female"] = float(g_female == 1.0 and waist_norm >= 0.35)
        result["waist_elevated_male"]   = float(g_female == 0.0 and waist_norm >= 0.65)
    return result


def score_profile(model, features: list[str], raw: dict) -> float:
    try:
        row   = pd.DataFrame([{f: raw.get(f, np.nan) for f in features}])
        score = float(model.predict_proba(row)[0, 1])
        return score
    except Exception:
        return float("nan")


def main():
    from model_runner import ModelRunner

    print("=" * 60)
    print("  Inflammation Missed-Positive Audit  (ML-INFLAM-02)")
    print("=" * 60)

    profiles = load_cohort(COHORT_PATH)

    runner = ModelRunner()
    norm   = runner._get_normalizer()

    # Load models (graceful skip if missing)
    models = {}
    if V3_PATH.exists():
        models["v3"] = joblib.load(V3_PATH)
    else:
        print(f"WARN: v3 model not found ({V3_PATH}), skipping v3")
    if V4_PATH.exists():
        models["v4"] = joblib.load(V4_PATH)
    else:
        print(f"WARN: v4 model not found ({V4_PATH}), skipping v4")

    # ── Filter to primary inflammation positives only (matches baseline counting) ──
    # profile_type=="positive" + target_condition=="inflammation" = the 49 primary profiles
    inflam_profiles = [
        p for p in profiles
        if p.get("target_condition") == "inflammation"
        and p.get("profile_type") == "positive"
    ]
    print(f"\nInflammation positives in cohort: {len(inflam_profiles)}")

    records = []
    for profile in inflam_profiles:
        raw_inputs = profile.get("nhanes_inputs", {})
        expected   = get_expected_conditions(profile)

        # Normalize through model_runner's normalizer (same path as live eval)
        try:
            fvecs      = norm.build_feature_vectors(raw_inputs)
            all_scores = runner.run_all_with_context(
                fvecs,
                patient_context={"gender": raw_inputs.get("gender"), "age_years": raw_inputs.get("age_years")},
            )
        except Exception as exc:
            print(f"  WARN: normalization failed: {exc}")
            continue

        # Get the normalized v3 feature row (includes waist_cm, most shared features)
        v3_fvec = fvecs.get("hidden_inflammation", pd.DataFrame())
        norm_row = v3_fvec.iloc[0].to_dict() if not v3_fvec.empty else {}
        enriched_row = derive_waist_flags(norm_row, raw_inputs)

        # Score v3 (from run_all_with_context — already normalized)
        s_v3 = all_scores.get("hidden_inflammation", float("nan"))

        # Score v4 (using enriched normalized row)
        if "v4" in models:
            try:
                v4_row  = pd.DataFrame([{f: enriched_row.get(f, float("nan")) for f in V4_FEATURES}])
                s_v4 = float(models["v4"].predict_proba(v4_row)[0, 1])
            except Exception:
                s_v4 = float("nan")
        else:
            s_v4 = float("nan")

        fires_v3 = s_v3 >= THRESHOLD_V3 if not np.isnan(s_v3) else False
        fires_v4 = s_v4 >= THRESHOLD_V4 if not np.isnan(s_v4) else False

        if fires_v4:
            group = "found_by_v4"
        elif fires_v3:
            group = "found_by_v3_only"
        else:
            group = "missed_both"

        # Generic-illness score from normalized features
        generic_vals = []
        for f in GENERIC_ILLNESS_FEATURES:
            v = enriched_row.get(f)
            try:
                fv = float(v)
                if not np.isnan(fv):
                    generic_vals.append(fv)
            except (TypeError, ValueError):
                pass
        generic_score = float(np.mean(generic_vals)) if generic_vals else float("nan")

        records.append({
            "profile_id":    profile.get("profile_id", "unknown"),
            "score_v3":      round(s_v3, 4) if not np.isnan(s_v3) else None,
            "score_v4":      round(s_v4, 4) if not np.isnan(s_v4) else None,
            "fires_v3":      fires_v3,
            "fires_v4":      fires_v4,
            "group":         group,
            "expected":      expected,
            "generic_score": round(generic_score, 4) if not np.isnan(generic_score) else None,
            "features":      {f: enriched_row.get(f) for f in GENERIC_ILLNESS_FEATURES + TRUE_INFLAMMATION_FEATURES},
        })

    # ── Group stats ───────────────────────────────────────────────────────────
    group_counter = Counter(r["group"] for r in records)
    print(f"\nGroup breakdown:")
    for g, n in group_counter.most_common():
        print(f"  {g:<22} {n:>3}  ({n / len(records):.0%})")

    # Feature means by group (generic-illness vs inflammation signal)
    group_features: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        for feat, val in r["features"].items():
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                group_features[r["group"]][feat].append(float(val))

    print("\nGeneric-illness feature means by group (lower = healthier / less ill):")
    print(f"{'Feature':<55}  {'found_v4':>10}  {'found_v3':>10}  {'missed':>10}")
    analysis_rows = []
    for feat in GENERIC_ILLNESS_FEATURES:
        means = {}
        for g in ["found_by_v4", "found_by_v3_only", "missed_both"]:
            vals = group_features[g].get(feat, [])
            means[g] = round(float(np.mean(vals)), 3) if vals else None
        print(
            f"  {feat:<53}  "
            f"{str(means.get('found_by_v4', '—')):>10}  "
            f"{str(means.get('found_by_v3_only', '—')):>10}  "
            f"{str(means.get('missed_both', '—')):>10}"
        )
        analysis_rows.append({"feature": feat, "type": "generic_illness", **means})

    print("\nTrue-inflammation feature means by group:")
    print(f"{'Feature':<55}  {'found_v4':>10}  {'found_v3':>10}  {'missed':>10}")
    for feat in TRUE_INFLAMMATION_FEATURES:
        means = {}
        for g in ["found_by_v4", "found_by_v3_only", "missed_both"]:
            vals = group_features[g].get(feat, [])
            means[g] = round(float(np.mean(vals)), 3) if vals else None
        print(
            f"  {feat:<53}  "
            f"{str(means.get('found_by_v4', '—')):>10}  "
            f"{str(means.get('found_by_v3_only', '—')):>10}  "
            f"{str(means.get('missed_both', '—')):>10}"
        )
        analysis_rows.append({"feature": feat, "type": "true_inflammation", **means})

    # ── Label fuzziness assessment ────────────────────────────────────────────
    n_missed = group_counter.get("missed_both", 0)
    n_total  = len(records)
    missed_pct = n_missed / n_total if n_total else 0

    # Compare missed_both vs found_by_v3_only (v4 finds nothing, so use v3 as reference)
    missed_records = [r for r in records if r["group"] == "missed_both"]
    found_records  = [r for r in records if r["group"] in {"found_by_v4", "found_by_v3_only"}]

    missed_gen_scores = [r["generic_score"] for r in missed_records if r["generic_score"] is not None]
    found_gen_scores  = [r["generic_score"] for r in found_records  if r["generic_score"] is not None]

    mean_missed = float(np.mean(missed_gen_scores)) if missed_gen_scores else None
    mean_found  = float(np.mean(found_gen_scores))  if found_gen_scores  else None

    # Heuristic: if missed positives have LOWER generic-illness scores than found ones,
    # those missed cases don't look sick by our features — possible label noise.
    fuzzy_label = False
    if mean_missed is not None and mean_found is not None:
        fuzzy_label = mean_missed < mean_found * 0.85  # 15% lower than found = suspicious

    print(f"\n── Label fuzziness assessment ───────────────────────────────────────")
    print(f"Missed-both:  {n_missed}/{n_total} ({missed_pct:.0%})")
    print(f"Mean generic-illness score — found: {mean_found}  |  missed: {mean_missed}")
    if fuzzy_label:
        print("⚠ Missed positives show LOWER generic-illness signal than found positives.")
        print("  This suggests the label may be capturing cases that don't match")
        print("  any consistent feature pattern — label redesign recommended.")
    else:
        print("✓ Missed positives look broadly similar to found positives.")
        print("  The problem is likely model capacity / feature coverage, not label noise.")

    # ── Save results ──────────────────────────────────────────────────────────
    audit = {
        "summary": {
            "n_inflam_profiles": n_total,
            "group_counts":      dict(group_counter),
            "fuzzy_label_flag":  fuzzy_label,
            "mean_generic_score_found":  mean_found,
            "mean_generic_score_missed": mean_missed,
        },
        "feature_analysis": analysis_rows,
        "profiles":         records,
    }
    out_json = RESULTS_DIR / "inflammation_missed_audit.json"
    out_json.write_text(json.dumps(audit, indent=2))
    print(f"\nSaved → {out_json}")

    # ── Markdown report ───────────────────────────────────────────────────────
    lines = [
        "# Inflammation Missed-Positive Audit — ML-INFLAM-02",
        "",
        f"**Cohort:** 760-profile NHANES balanced  |  **Inflammation positives:** {n_total}",
        "",
        "## Group Breakdown",
        "",
        "| Group | Count | % |",
        "|-------|-------|---|",
    ]
    for g, cnt in group_counter.most_common():
        lines.append(f"| {g} | {cnt} | {cnt / n_total:.0%} |")

    lines += [
        "",
        "## Label Fuzziness Assessment",
        "",
    ]
    if fuzzy_label:
        lines += [
            "**The label appears fuzzy.**",
            "",
            f"Missed positives have a lower generic-illness signal (mean={mean_missed}) than "
            f"found positives (mean={mean_found}). This means the model is not simply under-powered "
            "— the cases it misses don't look like typical inflammation by our current features.",
            "",
            "### Recommended Redesign",
            "",
            "1. **Split the label**: Separate `hidden_inflammation` into two sub-signals:",
            "   - `metabolic_inflammation` — central adiposity, low HDL, HTN, family DM",
            "   - `immune_inflammation` — arthritis type, frequent infections, anemia treatment",
            "2. **Feature audit**: Add CRP-proxies if available (hsCRP via NHANES lab data).",
            "3. **Negative re-labelling**: Review NHANES profiles currently labelled positive "
            "   but showing no feature signal — they may be label noise.",
        ]
    else:
        lines += [
            "**The label does not appear obviously fuzzy.**",
            "",
            f"Missed positives (generic score={mean_missed}) look similar to found positives "
            f"(generic score={mean_found}). The recall problem is likely in model capacity "
            "or missing discriminative features, not label quality.",
            "",
            "### Recommended Next Steps",
            "",
            "1. **Add lab features**: If NHANES hsCRP or ESR is available, add it — "
            "   it is the single best discrimination signal for inflammation.",
            "2. **Threshold sweep**: Run recall vs. precision curve to check if a lower "
            "   threshold recovers recall without excessive FPs.",
            "3. **Model architecture**: Swap LR for a gradient-boosted tree that can "
            "   capture non-linear waist × HDL × BP interactions.",
        ]

    out_md = RESULTS_DIR / "inflammation_missed_audit.md"
    out_md.write_text("\n".join(lines))
    print(f"Saved → {out_md}")
    print("\nDone.")


if __name__ == "__main__":
    main()
