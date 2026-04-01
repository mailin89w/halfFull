#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.roadmap_knn import (
    DEFAULT_ARTIFACT,
    KNN_K,
    disease_scores_from_neighbours,
    load_artifact,
    nearest_neighbours,
    recommend_missing_labs,
)


class RoadmapKNNScorer:
    def __init__(self, artifact_path: Path = DEFAULT_ARTIFACT) -> None:
        self.artifact_path = artifact_path
        self.artifact = load_artifact(artifact_path)

    def score(self, answers: dict[str, Any], *, k: int = KNN_K) -> dict[str, Any]:
        neighbour_idx, distances, overlap_counts = nearest_neighbours(answers, self.artifact, k=k)
        neighbour_seqns = self.artifact["index_seqns"][neighbour_idx]
        disease_scores = disease_scores_from_neighbours(neighbour_idx, distances, self.artifact)
        lab_signals, missing_lab_recommendations = recommend_missing_labs(answers, neighbour_idx, self.artifact)

        observed_locator_features = sum(
            1 for feature in self.artifact["feature_names"]
            if answers.get(feature) not in (None, "", [])
        )
        return {
            "disease_scores": disease_scores,
            "lab_signals": lab_signals,
            "missing_lab_recommendations": missing_lab_recommendations,
            "neighbor_seqns": [int(seqn) for seqn in neighbour_seqns],
            "neighbor_distances": [round(float(distance), 4) for distance in distances],
            "neighbor_overlap_features": [int(count) for count in overlap_counts],
            "n_neighbors": int(len(neighbour_seqns)),
            "query_feature_coverage": {
                "observed_locator_features": int(observed_locator_features),
                "total_locator_features": int(len(self.artifact["feature_names"])),
            },
        }


def main() -> int:
    payload = json.load(open(0))
    scorer = RoadmapKNNScorer()
    result = scorer.score(payload)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
