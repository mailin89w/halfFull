#!/usr/bin/env python3
"""
Build a dedicated real-profile comorbidity cohort from the NHANES balanced 760.

This cohort is intended for product-style evaluation of whether Layer 1 can
surface both clinically relevant conditions for users with meaningful
comorbidities. It tags each copied profile with one target pair so eval scripts
can compute pair-specific metrics like "both conditions in top-3".
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
INPUT_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"
OUTPUT_PATH = EVALS_DIR / "cohort" / "nhanes_comorbidity_pairs_v1.json"

COMORBIDITY_PAIRS: tuple[tuple[str, str], ...] = (
    ("anemia", "perimenopause"),
    ("prediabetes", "inflammation"),
    ("hypothyroidism", "sleep_disorder"),
    ("kidney_disease", "prediabetes"),
    ("hepatitis", "inflammation"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build real-profile comorbidity pair cohort.")
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--target-per-pair",
        type=int,
        default=None,
        help="Optional cap per pair. Defaults to all available real profiles.",
    )
    return parser.parse_args()


def _expected_conditions(profile: dict) -> set[str]:
    return {
        item["condition_id"]
        for item in profile.get("ground_truth", {}).get("expected_conditions", [])
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open() as f:
        profiles = json.load(f)

    rng = random.Random(args.seed)
    out: list[dict] = []
    pair_summary: dict[str, int] = {}

    for pair in COMORBIDITY_PAIRS:
        pair_set = set(pair)
        matches = [p for p in profiles if pair_set.issubset(_expected_conditions(p))]
        rng.shuffle(matches)
        if args.target_per_pair is not None:
            matches = matches[: args.target_per_pair]

        pair_id = f"{pair[0]}+{pair[1]}"
        pair_summary[pair_id] = len(matches)

        for idx, profile in enumerate(matches, start=1):
            clone = json.loads(json.dumps(profile))
            clone["profile_id"] = f"{profile['profile_id']}__{pair_id}__{idx:02d}"
            clone["profile_type"] = "multi"
            clone["target_condition"] = pair[0]
            metadata = dict(clone.get("metadata") or {})
            metadata["comorbidity_pair"] = list(pair)
            metadata["comorbidity_pair_id"] = pair_id
            metadata["comorbidity_pair_source_profile_id"] = profile["profile_id"]
            metadata["source_basis"] = "real_nhanes_balanced_760_pair_subset"
            clone["metadata"] = metadata
            out.append(clone)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(out)} profiles to {output_path}")
    for pair_id, n in pair_summary.items():
        print(f"  {pair_id}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
