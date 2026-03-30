#!/usr/bin/env python3
"""
build_nhanes_balanced_cohort.py

Builds a balanced 650-profile benchmark cohort from the pre-computed
NHANES 2003-2006 CSV (data/processed/nhanes_2003_2006_real_cohort.csv).

Key differences from the raw build script:
  - Vitamin D deficiency threshold tightened: < 50 → < 30 nmol/L
    (aligns with clinical "deficiency" vs the looser "insufficiency" cut)
  - Healthy profiles (0 conditions) are included and sampled
  - Output is balanced: up to TARGET_PER_CONDITION per condition,
    TARGET_HEALTHY healthy profiles, seed-stable

Output: evals/cohort/nhanes_balanced_650.json   (~650 profiles)
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

EVALS_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import helpers that build symptom vectors / Bayesian answers from the CSV row
from scripts.build_real_nhanes_2003_2006_cohort import (
    EVAL_CONDITION_LABELS,
    derive_activity_level,
    derive_smoking_status,
    fill_bayesian_answers,
    symptom_vector_from_row,
)

CSV_PATH    = PROJECT_ROOT / "data" / "processed" / "nhanes_2003_2006_real_cohort.csv"
OUTPUT_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_650.json"

# ── Sampling targets ──────────────────────────────────────────────────────────
TARGET_PER_CONDITION = 55   # per-condition cap (some rare conds have < 55)
TARGET_HEALTHY       = 100  # profiles with 0 conditions
SEED                 = 42

# ── Vitamin D threshold (tightened from the raw build's < 50) ─────────────────
VITD_THRESHOLD_NMOL_L = 30.0   # clinical "deficiency" — < 30 nmol/L = < 12 ng/mL

# Condition-to-canonical-id, inheriting from build script but adding vitamin_d
CONDITION_MAP: dict[str, str] = {
    "anemia":                    "anemia",
    "thyroid":                   "hypothyroidism",
    "sleep_disorder":            "sleep_disorder",
    "kidney":                    "kidney_disease",
    "hepatitis_bc":              "hepatitis",
    "liver":                     "liver",
    "menopause":                 "perimenopause",   # same thing
    "iron_deficiency":           "iron_deficiency",
    "electrolyte_imbalance":     "electrolyte_imbalance",
    "hidden_inflammation":       "inflammation",
    "prediabetes":               "prediabetes",
    "perimenopause_proxy_probable": "perimenopause",
    # vitamin_d re-evaluated below with tighter threshold
}

SMOKING_MAP: dict[str, str] = {
    "never":      "never",
    "not_at_all": "never",
    "former":     "former",
    "current":    "current",
    "daily":      "current",
    "some_days":  "current",
    "unknown":    "unknown",
}


def get_conditions(row: pd.Series) -> list[str]:
    """Return canonical condition IDs for a CSV row using tightened vitamin D threshold."""
    found: list[str] = []
    seen: set[str] = set()

    for csv_col, canon_id in CONDITION_MAP.items():
        val = row.get(csv_col)
        if pd.notna(val) and float(val) >= 0.5 and canon_id not in seen:
            found.append(canon_id)
            seen.add(canon_id)

    # Vitamin D — re-evaluate with tight threshold
    vd = row.get("vitamin_d_25oh_nmol_l")
    if pd.notna(vd) and float(vd) < VITD_THRESHOLD_NMOL_L:
        canon = "vitamin_d_deficiency"
        if canon not in seen:
            found.append(canon)

    return found


def build_profile(row: pd.Series, conditions: list[str]) -> dict[str, Any]:
    """Convert one CSV row + its condition list to the standard profile format."""
    symptom_vector = symptom_vector_from_row(row)
    bayesian_answers = fill_bayesian_answers(row, symptom_vector)
    activity = derive_activity_level(row)
    raw_smoking = derive_smoking_status(row)
    smoking = SMOKING_MAP.get(raw_smoking, "unknown")

    cycle = str(row.get("cycle", "?"))
    seqn  = int(row["SEQN"]) if pd.notna(row.get("SEQN")) else 0
    profile_id = f"NHANES-{cycle}-{seqn:05d}"

    if not conditions:
        profile_type     = "healthy"
        target_condition = None
        expected_conditions: list[dict] = []
    elif len(conditions) > 1:
        profile_type     = "multi"
        target_condition = conditions[0]
        expected_conditions = [
            {"condition_id": c, "is_primary": i == 0, "confidence": "high"}
            for i, c in enumerate(conditions)
        ]
    else:
        profile_type     = "positive"
        target_condition = conditions[0]
        expected_conditions = [
            {"condition_id": conditions[0], "is_primary": True, "confidence": "high"}
        ]

    return {
        "profile_id":       profile_id,
        "profile_type":     profile_type,
        "target_condition": target_condition,
        "source":           "real_nhanes_2003_2006",
        "seqn":             seqn,
        "demographics": {
            "age":            max(1, int(row["age_years"])) if pd.notna(row.get("age_years")) else 30,
            "sex":            "F" if str(row.get("gender", "")).lower() in ("female", "f") else "M",
            "bmi":            round(float(row["bmi"]), 2) if pd.notna(row.get("bmi")) else None,
            "smoking_status": smoking,
            "activity_level": activity,
        },
        "symptom_vector":   symptom_vector,
        "lab_values": {
            "ferritin":      _num(row, "ferritin_ng_ml"),
            "vitamin_b12":   _num(row, "vitamin_b12_serum_pg_ml"),
            "vitamin_d":     _num(row, "vitamin_d_25oh_nmol_l"),
            "hba1c":         _num(row, "hba1c_pct"),
            "creatinine":    _num(row, "serum_creatinine_mg_dl"),
            "crp":           _num(row, "crp_mg_l"),
            "hemoglobin":    _num(row, "hemoglobin_g_dl"),
            "alt":           _num(row, "alt_u_l"),
            "ast":           _num(row, "ast_u_l"),
            "ggt":           _num(row, "ggt_u_l"),
            "albumin":       _num(row, "serum_albumin_g_dl"),
            "wbc":           _num(row, "wbc_1000_cells_ul"),
            "total_protein": _num(row, "total_protein_g_dl"),
        },
        "quiz_path": "hybrid",
        "bayesian_answers": bayesian_answers,
        "ground_truth": {
            "expected_conditions": expected_conditions,
        },
        "metadata": {
            "cycle":          cycle,
            "vitd_threshold": VITD_THRESHOLD_NMOL_L,
            "source_basis":   "real_nhanes_2003_2006",
        },
    }


def _num(row: pd.Series, col: str) -> float | None:
    v = row.get(col)
    return None if pd.isna(v) else round(float(v), 2)


def main() -> int:
    print(f"Reading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"  {len(df):,} rows loaded")

    # ── Classify rows ─────────────────────────────────────────────────────────
    print("Classifying conditions (vitamin D threshold < 30 nmol/L) ...")
    df["_conditions"] = df.apply(get_conditions, axis=1)
    df["_n_conds"]    = df["_conditions"].apply(len)

    labeled_df  = df[df["_n_conds"] > 0].copy()
    healthy_df  = df[df["_n_conds"] == 0].copy()

    print(f"  Labeled rows  : {len(labeled_df):,}")
    print(f"  Healthy rows  : {len(healthy_df):,}")

    # ── Sample balanced labeled profiles ──────────────────────────────────────
    rng = random.Random(SEED)

    # Group by primary condition
    by_condition: dict[str, list[int]] = defaultdict(list)
    for idx, row in labeled_df.iterrows():
        conds = row["_conditions"]
        if conds:
            by_condition[conds[0]].append(idx)

    print()
    print("Sampling labeled profiles:")
    sampled_indices: list[int] = []
    for cond in sorted(by_condition):
        pool = by_condition[cond]
        n    = min(TARGET_PER_CONDITION, len(pool))
        chosen = rng.sample(pool, n)
        sampled_indices.extend(chosen)
        print(f"  {cond:35s} available={len(pool):5,}  sampled={n}")

    # ── Sample healthy profiles ───────────────────────────────────────────────
    healthy_pool = list(healthy_df.index)
    n_healthy    = min(TARGET_HEALTHY, len(healthy_pool))
    healthy_chosen = rng.sample(healthy_pool, n_healthy)
    print(f"\n  {'healthy':35s} available={len(healthy_pool):5,}  sampled={n_healthy}")

    # ── Build profile objects ─────────────────────────────────────────────────
    print("\nBuilding profile objects ...")
    all_selected = df.loc[sampled_indices + healthy_chosen]
    profiles: list[dict[str, Any]] = []
    for _, row in all_selected.iterrows():
        try:
            p = build_profile(row, row["_conditions"])
            profiles.append(p)
        except Exception as e:
            print(f"  WARN: skipping SEQN={row.get('SEQN')} — {e}")

    rng.shuffle(profiles)

    # ── Summary ───────────────────────────────────────────────────────────────
    from collections import Counter
    type_counts = Counter(p["profile_type"] for p in profiles)
    cond_counts = Counter(p["target_condition"] for p in profiles if p["target_condition"])

    print()
    print("Final cohort:")
    print(f"  Total   : {len(profiles):,}")
    print(f"  Types   : {dict(sorted(type_counts.items()))}")
    print(f"  Conditions (primary):")
    for c, n in sorted(cond_counts.items(), key=lambda x: -x[1]):
        print(f"    {c:35s} {n}")

    # ── Write output ──────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(profiles, indent=2))
    mb = OUTPUT_PATH.stat().st_size / 1_048_576
    print(f"\nWrote {OUTPUT_PATH.name}  ({mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
