"""
thyroid_lr_l2_18feat — inference helper
========================================
Loads the saved LR L2 pipeline and scores new records.

Usage
-----
    from models.predict import ThyroidPredictor
    pred = ThyroidPredictor()                     # loads model + metadata
    scores = pred.predict_proba(df_new)           # raw probabilities
    flags  = pred.predict(df_new)                 # binary, default thr=0.3
    flags  = pred.predict(df_new, threshold=0.41) # binary, screening thr

    # single patient dict
    score = pred.score_one({"age_years": 58, "gender": 2, "med_count": 4, ...})

Quick start (standalone)
------------------------
    python models/predict.py
"""

import os, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_DIR   = os.path.dirname(os.path.abspath(__file__))
_MODEL = os.path.join(_DIR, "thyroid_lr_l2_18feat.joblib")
_META  = os.path.join(_DIR, "thyroid_lr_l2_18feat_metadata.json")


class ThyroidPredictor:
    """
    Wrapper around the saved sklearn Pipeline.

    The pipeline expects exactly the 25 columns listed in metadata
    (18 base features + 7 missingness flags).  This class handles
    missingness-flag creation automatically — just pass the 18 base
    features (or a subset; missing ones become NaN).

    Parameters
    ----------
    model_path : str, optional
        Path to the .joblib file.  Defaults to models/thyroid_lr_l2_18feat.joblib
    threshold  : float, optional
        Default decision threshold for predict().  0.3 = maximum recall.
        Use 0.41 for the ≥85% recall / higher precision operating point.
    """

    BASE_FEATURES = [
        "age_years", "gender", "med_count", "avg_drinks_per_day",
        "general_health_condition", "doctor_said_overweight",
        "told_dr_trouble_sleeping", "tried_to_lose_weight", "avg_cigarettes_per_day",
        "weight_kg", "pregnancy_status", "moderate_recreational",
        "times_urinate_in_night", "overall_work_schedule", "ever_told_high_cholesterol",
        "ever_told_diabetes", "taking_anemia_treatment", "sleep_hours_weekdays",
    ]

    def __init__(self, model_path: str = _MODEL, threshold: float = 0.3):
        import joblib
        self.pipeline  = joblib.load(model_path)
        self.threshold = threshold
        with open(_META) as f:
            self.metadata = json.load(f)
        self.all_features = self.metadata["all_features"]   # 25 cols incl. flags
        self.miss_flags   = self.metadata["miss_flag_features"]

    # ── public API ────────────────────────────────────────────────────────────

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return thyroid-positive probabilities, shape (n_samples,)."""
        Xp = self._prepare(X)
        return self.pipeline.predict_proba(Xp)[:, 1]

    def predict(self, X: pd.DataFrame, threshold: float | None = None) -> np.ndarray:
        """Return binary predictions (1 = likely thyroid disease)."""
        thr = threshold if threshold is not None else self.threshold
        return (self.predict_proba(X) >= thr).astype(int)

    def score_one(self, record: dict, threshold: float | None = None) -> dict:
        """
        Score a single patient dict.  Returns probability + flag.

        Example
        -------
        pred.score_one({
            "age_years": 62, "gender": 2, "med_count": 3,
            "avg_drinks_per_day": 0, "general_health_condition": 3,
        })
        """
        row = pd.DataFrame([record])
        prob = float(self.predict_proba(row)[0])
        thr  = threshold if threshold is not None else self.threshold
        return {
            "thyroid_probability": round(prob, 4),
            "threshold_used":      thr,
            "flagged":             bool(prob >= thr),
        }

    def feature_importance(self) -> pd.DataFrame:
        """Return a DataFrame of feature names and their model coefficients."""
        coefs = self.pipeline.named_steps["clf"].coef_[0]
        return (
            pd.DataFrame({"feature": self.all_features, "coefficient": coefs})
            .sort_values("coefficient", key=abs, ascending=False)
            .reset_index(drop=True)
        )

    def summary(self) -> None:
        """Print a human-readable model card."""
        m = self.metadata
        ho = m["holdout_eval"]
        cv = m["cv_5fold"]
        print(f"{'─'*55}")
        print(f"  {m['model_name']}  v{m['model_version']}")
        print(f"{'─'*55}")
        print(f"  {m['description']}")
        print(f"\n  Training data:  N={m['n_train_total']:,}  "
              f"positives={m['n_positive']} ({m['prevalence_pct']}%)")
        print(f"  Base features:  {len(m['base_features'])}"
              f"  +  {len(m['miss_flag_features'])} missingness flags"
              f"  =  {m['n_features_total']} total")
        print(f"\n  Hold-out (20%):  AUC={ho['roc_auc']}  "
              f"Recall@{m['threshold_default']}={ho['recall_at_default_thr']}  "
              f"Precision@{m['threshold_default']}={ho['precision_at_default_thr']}")
        print(f"  CV 5-fold:       AUC={cv['roc_auc_mean']}±{cv['roc_auc_std']}")
        print(f"\n  Thresholds:")
        print(f"    thr={m['threshold_default']}  → max recall  "
              f"(recall={ho['recall_at_default_thr']}, "
              f"precision={ho['precision_at_default_thr']})")
        print(f"    thr={m['threshold_screening']} → recall≥85%  "
              f"(recall={ho['recall_at_screening_thr']}, "
              f"precision={ho['precision_at_screening_thr']})")
        print(f"{'─'*55}")

    # ── internals ─────────────────────────────────────────────────────────────

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        """Ensure all expected columns exist (add NaN if missing), add miss flags."""
        X = X.copy()
        # ensure all base features present
        for col in self.BASE_FEATURES:
            if col not in X.columns:
                X[col] = np.nan
        # add missingness flags
        for col in self.BASE_FEATURES:
            flag = f"{col}_miss"
            if flag in self.all_features:
                X[flag] = X[col].isnull().astype(int)
        # return in correct column order
        return X[self.all_features]


# ── standalone demo ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    pred = ThyroidPredictor()
    pred.summary()

    print("\nTop 10 features by |coefficient|:")
    print(pred.feature_importance().head(10).to_string(index=False))

    # single-record example
    example = {
        "age_years": 58, "gender": 2, "med_count": 4,
        "avg_drinks_per_day": 0.0, "general_health_condition": 3,
        "doctor_said_overweight": 1, "told_dr_trouble_sleeping": 1,
        "tried_to_lose_weight": 1, "avg_cigarettes_per_day": 0.0,
        "weight_kg": 82.0, "pregnancy_status": 0,
        "moderate_recreational": 0, "times_urinate_in_night": 2,
        "overall_work_schedule": 1, "ever_told_high_cholesterol": 1,
        "ever_told_diabetes": 0, "taking_anemia_treatment": 0,
        "sleep_hours_weekdays": 7.0,
    }
    result = pred.score_one(example)
    print(f"\nSample prediction: {result}")
