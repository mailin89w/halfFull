#!/usr/bin/env python3
"""
run_eval.py — HalfFull evaluation pipeline entry point.

Runs synthetic profiles through the full eval pipeline:
  ProfileLoader -> QuizSimulatorAdapter -> MedGemmaAdapter ->
  ResponseParser -> ScoringEngine -> MetricsAggregator -> Report

Usage:
    python run_eval.py [OPTIONS]

See README.md or docs/how_to_run_evals.md for full usage guide.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

try:
    from tqdm import tqdm
    _TQDM_AVAILABLE = True
except ImportError:
    _TQDM_AVAILABLE = False

from pipeline.profile_loader import ProfileLoader
from pipeline.quiz_simulator_adapter import QuizSimulatorAdapter
from pipeline.medgemma_adapter import MedGemmaAdapter
from pipeline.response_parser import ResponseParser
from pipeline.scoring_engine import ScoringEngine
from pipeline.metrics_aggregator import MetricsAggregator

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
PROFILES_PATH = EVALS_DIR / "cohort" / "profiles.json"
SCHEMA_PATH   = EVALS_DIR / "schema" / "profile_schema.json"
RESULTS_DIR   = EVALS_DIR / "results"
REPORTS_DIR   = EVALS_DIR / "reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_eval")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run HalfFull synthetic evaluation pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_eval.py --dry-run --n 10
  python run_eval.py --no-medgemma --n 50
  python run_eval.py --layer 1
  python run_eval.py --condition menopause --type positive
        """,
    )
    parser.add_argument(
        "--layer", type=int, default=1, choices=[1, 4],
        help="Eval layer: 1 (condition-first) or 4 (co-morbidity). Default: 1",
    )
    parser.add_argument(
        "--n", type=int, default=None,
        help="Number of profiles to run. Default: all",
    )
    parser.add_argument(
        "--condition", type=str, default=None,
        help="Run only profiles targeting this condition ID",
    )
    parser.add_argument(
        "--type", dest="profile_type", type=str, default=None,
        choices=["positive", "borderline", "negative", "healthy", "edge"],
        help="Run only profiles of this type",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Load and validate profiles only — no inference",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Override results output directory",
    )
    parser.add_argument(
        "--no-medgemma", action="store_true",
        help="Skip MedGemma inference; run scoring layer only (fast iteration)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for sampling when --n < total profiles",
    )
    return parser.parse_args()


def load_profiles(
    args: argparse.Namespace,
    loader: ProfileLoader,
) -> list[dict]:
    """Load and filter profiles according to CLI args."""
    if args.condition:
        profiles = loader.load_by_condition(args.condition)
        logger.info("Filtered to condition '%s': %d profiles", args.condition, len(profiles))
    elif args.profile_type:
        profiles = loader.load_by_type(args.profile_type)
        logger.info("Filtered to type '%s': %d profiles", args.profile_type, len(profiles))
    else:
        profiles = loader.load_all()
        logger.info("Loaded %d profiles", len(profiles))

    if args.n is not None and args.n < len(profiles):
        rng = random.Random(args.seed)
        profiles = rng.sample(profiles, args.n)
        logger.info("Sampled %d profiles (seed=%d)", args.n, args.seed)

    return profiles


def make_null_result(profile: dict) -> dict:
    """Build a no-inference result (dry-run or --no-medgemma with no scoring)."""
    return {
        "profile_id":            profile.get("profile_id", ""),
        "profile_type":          profile.get("profile_type", ""),
        "target_condition":      profile.get("target_condition"),
        "quiz_path":             profile.get("quiz_path", "full"),
        "parse_success":         False,
        "model_top1":            None,
        "model_top1_confidence": None,
        "top1_correct":          None,
        "hallucinated_ids":      [],
        "ground_truth_primary":  None,
        "_model_output":         None,
    }


def print_dod_table(report: dict) -> None:
    """Print DoD summary table with pass/fail indicators."""
    print()
    print("=" * 60)
    print(" DoD Summary")
    print("=" * 60)
    print(f"{'Metric':<35} {'Target':>8}  {'Actual':>8}  {'Status':>6}")
    print("-" * 60)

    for metric, check in report["dod_checks"].items():
        status = "PASS" if check["pass"] else "FAIL"
        print(
            f"{metric:<35} {check['target']:>8.0%}  {check['actual']:>8.1%}  {status}"
        )

    print("-" * 60)
    overall = "ALL DoD TARGETS MET" if report["dod_pass"] else "SOME DoD TARGETS FAILED"
    print(f" {overall}")
    print("=" * 60)
    print()


def main() -> int:
    args = parse_args()

    results_dir = Path(args.output) if args.output else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # -- Load profiles ----------------------------------------------------
    loader = ProfileLoader(PROFILES_PATH, SCHEMA_PATH)
    try:
        profiles = load_profiles(args, loader)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    if not profiles:
        logger.error("No profiles matched the given filters. Exiting.")
        return 1

    # -- Dry run: validate only -------------------------------------------
    if args.dry_run:
        print(f"\nDry run complete. Loaded and validated {len(profiles)} profiles.\n")
        return 0

    # -- Pipeline components ----------------------------------------------
    quiz_adapter    = QuizSimulatorAdapter()
    medgemma        = MedGemmaAdapter() if not args.no_medgemma else None
    response_parser = ResponseParser()
    scoring_engine  = ScoringEngine()
    aggregator      = MetricsAggregator()

    results: list[dict] = []
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # -- Main eval loop ---------------------------------------------------
    iterator = (
        tqdm(profiles, desc="Evaluating", unit="profile")
        if _TQDM_AVAILABLE
        else profiles
    )

    for profile in iterator:
        try:
            # Step 2a: Quiz simulation
            quiz_output = quiz_adapter.run(profile)

            if args.no_medgemma:
                # Skip MedGemma — score with null output
                result = scoring_engine.score_profile(profile, None, False)
            else:
                # Step 2b: MedGemma inference
                raw_response = None
                parse_success = False
                model_output = None

                try:
                    raw_response = medgemma.query(quiz_output, profile)
                    model_output = response_parser.parse(raw_response)
                    parse_success = (
                        model_output is not None and
                        response_parser.is_valid(model_output)
                    )
                except Exception as exc:
                    logger.warning(
                        "MedGemma error for profile %s: %s",
                        profile.get("profile_id", "?"),
                        exc,
                    )
                    parse_success = False
                    model_output = None

                # Step 2d: Score
                result = scoring_engine.score_profile(profile, model_output, parse_success)

            results.append(result)

        except Exception as exc:
            logger.error(
                "Unexpected error processing profile %s: %s",
                profile.get("profile_id", "?"),
                exc,
                exc_info=True,
            )
            results.append(make_null_result(profile))

    # -- Aggregate metrics ------------------------------------------------
    report = aggregator.aggregate(results, scoring_engine)

    # -- Write results JSON -----------------------------------------------
    results_path = results_dir / f"eval_run_{timestamp}.json"
    # Remove private keys before writing
    clean_results = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in results
    ]
    with results_path.open("w") as f:
        json.dump({"report": report, "results": clean_results}, f, indent=2)
    logger.info("Results written to %s", results_path)

    # -- Write Markdown report --------------------------------------------
    report_path = REPORTS_DIR / f"eval_report_{timestamp}.md"
    md_report = aggregator.to_markdown(report)
    with report_path.open("w") as f:
        f.write(md_report)
    logger.info("Report written to %s", report_path)

    # -- Print DoD table --------------------------------------------------
    print_dod_table(report)

    return 0 if report["dod_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
