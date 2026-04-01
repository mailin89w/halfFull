#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_COHORT = Path("/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_800.json")
BACKFILL_VERSION = "20260401_binary_backfill_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill binary Bayes answers for stale schema questions.")
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    return parser.parse_args()


def stable_noise(profile_id: str, question_id: str) -> float:
    digest = hashlib.sha256(f"{profile_id}|{question_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def numeric(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def yes_no(prob_yes: float, profile_id: str, question_id: str) -> str:
    return "yes" if stable_noise(profile_id, question_id) < clip01(prob_yes) else "no"


def expected_ids(profile: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in profile.get("ground_truth", {}).get("expected_conditions", []) or []:
        if isinstance(item, dict):
            condition_id = item.get("condition_id")
            if condition_id:
                ids.add(str(condition_id))
        elif isinstance(item, str):
            ids.add(item)
    return ids


def derive_anemia_q5(profile: dict[str, Any]) -> str:
    pid = profile["profile_id"]
    answers = profile.get("nhanes_inputs", {}) or {}
    labels = expected_ids(profile)

    fatigue = numeric(answers.get("dpq040_fatigue")) or 0.0
    fatigue = min(max(fatigue / 3.0, 0.0), 1.0)
    sob_stairs = numeric(answers.get("cdq010_sob_stairs")) == 1.0
    poor_health = numeric(answers.get("huq010_general_health_condition"))
    poor_health = 1.0 if (poor_health is not None and poor_health >= 4) else 0.0
    female = str(profile.get("demographics", {}).get("sex", "")).upper() == "F"
    age = numeric(profile.get("demographics", {}).get("age")) or 45.0

    prob = 0.08
    if "anemia" in labels:
        prob += 0.46
    if "iron_deficiency" in labels:
        prob += 0.24
    if "kidney_disease" in labels:
        prob += 0.12
    if "liver" in labels or "hepatitis" in labels:
        prob += 0.08
    if sob_stairs:
        prob += 0.18
    prob += 0.10 * fatigue
    prob += 0.06 * poor_health
    if female and 35 <= age <= 55:
        prob += 0.04

    return yes_no(prob, pid, "anemia_q5")


def derive_inflam_q4(profile: dict[str, Any]) -> str:
    pid = profile["profile_id"]
    answers = profile.get("nhanes_inputs", {}) or {}
    labels = expected_ids(profile)

    arthritis = numeric(answers.get("mcq160a_arthritis")) == 1.0
    abdominal_pain = numeric(answers.get("mcq520_abdominal_pain")) == 1.0
    fatigue = numeric(answers.get("dpq040_fatigue")) or 0.0
    fatigue = min(max(fatigue / 3.0, 0.0), 1.0)
    poor_health = numeric(answers.get("huq010_general_health_condition"))
    poor_health = 1.0 if (poor_health is not None and poor_health >= 4) else 0.0

    prob = 0.05
    if "inflammation" in labels:
        prob += 0.43
    if "hepatitis" in labels:
        prob += 0.12
    if "liver" in labels:
        prob += 0.08
    if "sleep_disorder" in labels:
        prob += 0.02
    if arthritis:
        prob += 0.15
    if abdominal_pain:
        prob += 0.10
    prob += 0.07 * fatigue
    prob += 0.04 * poor_health

    return yes_no(prob, pid, "inflam_q4")


def main() -> int:
    args = parse_args()
    profiles = json.loads(args.cohort.read_text(encoding="utf-8"))

    for profile in profiles:
        bayes = profile.setdefault("bayesian_answers", {})
        bayes["anemia_q5"] = derive_anemia_q5(profile)
        bayes["inflam_q4"] = derive_inflam_q4(profile)
        metadata = profile.setdefault("metadata", {})
        metadata["binary_bayes_backfill_version"] = BACKFILL_VERSION

    args.cohort.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
    print(args.cohort)
    print(BACKFILL_VERSION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
