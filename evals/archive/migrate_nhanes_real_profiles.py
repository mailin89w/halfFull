#!/usr/bin/env python3
"""
migrate_nhanes_real_profiles.py

Converts nhanes_2003_2006_real_profiles.json from its raw build format to the
standard profile schema used by ProfileLoader and all eval scripts.

Raw format (ground_truth as list):
  "ground_truth": [{"condition": "menopause", "confidence": "high", "rank": 1}]

Target format (ground_truth as dict with expected_conditions):
  "ground_truth": {
    "expected_conditions": [{"condition_id": "perimenopause", "is_primary": true}]
  }

Also adds:
  - profile_type  ("positive" / "multi" / "healthy")
  - target_condition  (primary condition_id, or None for healthy)

Condition name mapping (raw → canonical condition_id):
  menopause         → perimenopause   (user confirmed: same thing)
  thyroid           → hypothyroidism  (user confirmed: same thing)
  hypothyroidism    → hypothyroidism  (already correct)
  kidney_disease    → kidney_disease
  electrolyte_imbalance → electrolyte_imbalance
  iron_deficiency   → iron_deficiency
  sleep_disorder    → sleep_disorder
  anemia            → anemia
  liver             → liver
  hepatitis         → hepatitis
  prediabetes       → prediabetes
  inflammation      → inflammation
  perimenopause     → perimenopause

Profiles with no mappable conditions → profile_type="healthy"
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent

INPUT_PATH  = EVALS_DIR / "cohort" / "nhanes_2003_2006_real_profiles.json"
OUTPUT_PATH = EVALS_DIR / "cohort" / "nhanes_2003_2006_profiles_migrated.json"

# Raw condition name → canonical condition_id (from condition_ids.json)
SMOKING_MAP: dict[str, str] = {
    "never":      "never",
    "not_at_all": "never",
    "former":     "former",
    "current":    "current",
    "daily":      "current",
    "some_days":  "current",
    "unknown":    "unknown",
}

CONDITION_MAP: dict[str, str] = {
    "menopause":            "perimenopause",
    "perimenopause":        "perimenopause",
    "thyroid":              "hypothyroidism",
    "hypothyroidism":       "hypothyroidism",
    "kidney_disease":       "kidney_disease",
    "electrolyte_imbalance":"electrolyte_imbalance",
    "iron_deficiency":      "iron_deficiency",
    "sleep_disorder":       "sleep_disorder",
    "anemia":               "anemia",
    "liver":                "liver",
    "hepatitis":            "hepatitis",
    "prediabetes":          "prediabetes",
    "inflammation":         "inflammation",
    "vitamin_b12_deficiency": "vitamin_b12_deficiency",
    "vitamin_d_deficiency":   "vitamin_d_deficiency",
}


def migrate_profile(raw: dict) -> dict:
    """Convert one raw NHANES profile to the standard eval schema."""
    raw_gt: list[dict] = raw.get("ground_truth", [])

    # Sort by rank so primary (rank=1) comes first
    sorted_gt = sorted(raw_gt, key=lambda x: x.get("rank", 99))

    expected_conditions = []
    skipped = []
    for item in sorted_gt:
        raw_name = item.get("condition", "")
        mapped = CONDITION_MAP.get(raw_name)
        if mapped is None:
            skipped.append(raw_name)
            continue
        expected_conditions.append({
            "condition_id": mapped,
            "is_primary": len(expected_conditions) == 0,  # first valid = primary
            "confidence": item.get("confidence", "high"),
        })

    # Deduplicate (menopause + perimenopause can both map to perimenopause)
    seen: set[str] = set()
    deduped = []
    for ec in expected_conditions:
        if ec["condition_id"] not in seen:
            seen.add(ec["condition_id"])
            deduped.append(ec)
    expected_conditions = deduped

    # Assign profile_type
    if not expected_conditions:
        profile_type = "healthy"
        target_condition = None
    elif len(expected_conditions) > 1:
        profile_type = "multi"
        target_condition = expected_conditions[0]["condition_id"]
    else:
        profile_type = "positive"
        target_condition = expected_conditions[0]["condition_id"]

    demo = dict(raw.get("demographics", {}))
    raw_smoking = demo.get("smoking_status", "unknown")
    demo["smoking_status"] = SMOKING_MAP.get(raw_smoking, "unknown")

    migrated = {
        "profile_id":       raw["profile_id"],
        "profile_type":     profile_type,
        "target_condition": target_condition,
        "source":           raw.get("source", "real_nhanes_2003_2006"),
        "seqn":             raw.get("seqn"),
        "demographics":     demo,
        "symptom_vector":   raw.get("symptom_vector", {}),
        "lab_values":       raw.get("lab_values", {}),
        "quiz_path":        "hybrid",
        "bayesian_answers": raw.get("bayesian_answers", {}),
        "ground_truth": {
            "expected_conditions": expected_conditions,
        },
        "metadata":         raw.get("metadata", {}),
    }

    if skipped:
        migrated["metadata"]["skipped_conditions"] = skipped

    return migrated


def main() -> int:
    print(f"Reading {INPUT_PATH} ...")
    raw_profiles: list[dict] = json.loads(INPUT_PATH.read_text())
    print(f"  {len(raw_profiles):,} raw profiles loaded")

    migrated_profiles = []
    type_counts: Counter = Counter()
    condition_counts: Counter = Counter()
    skipped_counts: Counter = Counter()

    for raw in raw_profiles:
        m = migrate_profile(raw)
        migrated_profiles.append(m)
        type_counts[m["profile_type"]] += 1
        if m["target_condition"]:
            condition_counts[m["target_condition"]] += 1
        for sc in m.get("metadata", {}).get("skipped_conditions", []):
            skipped_counts[sc] += 1

    print()
    print("Migration summary:")
    print(f"  Total profiles  : {len(migrated_profiles):,}")
    print()
    print("  Profile types:")
    for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:12s} {n:5,}")
    print()
    print("  Primary conditions (target_condition):")
    for c, n in sorted(condition_counts.items(), key=lambda x: -x[1]):
        print(f"    {c:30s} {n:5,}")
    if skipped_counts:
        print()
        print("  Skipped / unmapped condition names:")
        for c, n in sorted(skipped_counts.items(), key=lambda x: -x[1]):
            print(f"    {c:30s} {n:5,}  ← add to CONDITION_MAP if needed")

    print()
    print(f"Writing {OUTPUT_PATH} ...")
    OUTPUT_PATH.write_text(json.dumps(migrated_profiles, indent=2))
    size_mb = OUTPUT_PATH.stat().st_size / 1_048_576
    print(f"  Done — {size_mb:.1f} MB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
