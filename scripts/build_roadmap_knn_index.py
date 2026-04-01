#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.roadmap_knn import (
    DEFAULT_ARTIFACT,
    DEFAULT_DISEASES_FILE,
    DEFAULT_FINAL_FILE,
    DEFAULT_REF_RANGES_FILE,
    DEFAULT_ROADMAP_CSV,
    build_artifact,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build roadmap-driven KNN inference artifact.")
    parser.add_argument("--roadmap-csv", type=Path, default=DEFAULT_ROADMAP_CSV)
    parser.add_argument("--final-file", type=Path, default=DEFAULT_FINAL_FILE)
    parser.add_argument("--diseases-file", type=Path, default=DEFAULT_DISEASES_FILE)
    parser.add_argument("--ref-ranges-file", type=Path, default=DEFAULT_REF_RANGES_FILE)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = build_artifact(
        roadmap_csv=args.roadmap_csv,
        final_file=args.final_file,
        diseases_file=args.diseases_file,
        ref_ranges_file=args.ref_ranges_file,
        artifact_path=args.artifact,
    )
    print(f"Saved roadmap KNN artifact: {args.artifact}")
    print(f"Index rows: {len(artifact['index_seqns'])}")
    print(f"Locator features: {len(artifact['feature_names'])}")
    print(f"Disease labels: {len(artifact['disease_cols'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
