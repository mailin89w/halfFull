#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.build_nhanes_balanced_cohort import build_profile, get_conditions

BASE_COHORT_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"
SOURCE_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "nhanes_2003_2006_real_cohort.csv"
OUTPUT_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_800.json"

TARGET_TOTAL = 800
TARGET_PERIMENOPAUSE_PRIMARY = 55
HEALTHY_TRIM = 6
SEED = 20260331


def _is_healthy(profile: dict) -> bool:
    return profile.get("target_condition") is None and not profile.get("ground_truth", {}).get("expected_conditions", [])


def main() -> int:
    rng = random.Random(SEED)

    base_profiles = json.loads(BASE_COHORT_PATH.read_text())
    base_seqn = {int(p["seqn"]) for p in base_profiles if p.get("seqn") is not None}

    perimenopause_primary = [p for p in base_profiles if p.get("target_condition") == "perimenopause"]
    healthy_profiles = [p for p in base_profiles if _is_healthy(p)]
    non_healthy_profiles = [p for p in base_profiles if not _is_healthy(p)]

    needed_peri = max(0, TARGET_PERIMENOPAUSE_PRIMARY - len(perimenopause_primary))
    if needed_peri == 0:
        raise SystemExit("Base cohort already has enough primary perimenopause profiles.")

    if len(healthy_profiles) < HEALTHY_TRIM:
        raise SystemExit("Not enough healthy profiles to trim for the 800-person rebuild.")

    df = pd.read_csv(SOURCE_CSV_PATH, low_memory=False)
    df["_conditions"] = df.apply(get_conditions, axis=1)

    eligible = df[
        df["age_years"].between(35, 55, inclusive="both")
        & df["_conditions"].apply(lambda xs: len(xs) > 0 and xs[0] == "perimenopause")
        & ~df["SEQN"].isin(base_seqn)
    ].copy()

    if len(eligible) < needed_peri:
        raise SystemExit(
            f"Need {needed_peri} unseen primary perimenopause rows, found only {len(eligible)}."
        )

    chosen_rows = eligible.sample(n=needed_peri, random_state=SEED)
    new_profiles = [build_profile(row, row["_conditions"]) for _, row in chosen_rows.iterrows()]

    for profile in new_profiles:
        profile.setdefault("metadata", {})["source_basis"] = "real_nhanes_2003_2006_topup_for_balanced_800"
        profile["metadata"]["build_variant"] = "balanced_800_perimenopause_restored"

    healthy_trimmed = healthy_profiles.copy()
    drop_indices = sorted(rng.sample(range(len(healthy_trimmed)), HEALTHY_TRIM), reverse=True)
    for idx in drop_indices:
        healthy_trimmed.pop(idx)

    final_profiles = non_healthy_profiles + healthy_trimmed + new_profiles
    rng.shuffle(final_profiles)

    if len(final_profiles) != TARGET_TOTAL:
        raise SystemExit(f"Expected {TARGET_TOTAL} profiles, got {len(final_profiles)}.")

    counts = Counter(p.get("target_condition") for p in final_profiles)
    OUTPUT_PATH.write_text(json.dumps(final_profiles, indent=2) + "\n")

    print(
        {
            "output": str(OUTPUT_PATH),
            "total_profiles": len(final_profiles),
            "primary_counts": dict(counts),
            "added_perimenopause": len(new_profiles),
            "trimmed_healthy": HEALTHY_TRIM,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
