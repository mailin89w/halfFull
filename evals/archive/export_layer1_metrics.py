#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from layer1_metrics_exporter import build_layer1_metrics_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export canonical Layer 1 slide/UI metrics from a saved eval JSON.")
    parser.add_argument("input", help="Path to layer1 results JSON")
    parser.add_argument("--output", default=None, help="Optional explicit output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    payload = json.loads(input_path.read_text())
    exported = build_layer1_metrics_export(payload)

    output_path = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + "_metrics_export.json"
    )
    output_path.write_text(json.dumps(exported, indent=2) + "\n")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
