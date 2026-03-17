"""KidneyPredictor — standalone inference wrapper for kidney CKD LR models.

Two model variants are available:
  - 'full'    : kidney_lr_l2_52feat  — 52 base features (labs + quest), AUC=0.9037
  - 'routine' : kidney_lr_l2_routine_30feat — 30 base features (routine GP only), AUC=0.7772
"""
import json
import pathlib
import joblib
import numpy as np
import pandas as pd

MODEL_DIR = pathlib.Path(__file__).parent

_MODEL_FILES = {
    "full":    "kidney_lr_l2_52feat.joblib",
    "routine": "kidney_lr_l2_routine_30feat.joblib",
}


class KidneyPredictor:
    """Wraps a kidney CKD LR pipeline for easy inference.

    Quick start:
        p = KidneyPredictor()                        # full model (default)
        p = KidneyPredictor(model_type='routine')    # routine-only model
        p.summary()
        prob = p.predict_proba(df)                   # array of scores 0-1
        flags = p.predict(df, threshold=0.48)        # binary at screening thr
        result = p.score_one({'age_years': 65, 'creatinine_serum': 1.5, ...})
    """

    def __init__(self, model_type: str = "full", model_path=None, meta_path=None):
        """
        Parameters
        ----------
        model_type : str
            'full'    — 52-feature model with labs + questionnaire (AUC=0.9037).
            'routine' — 30-feature routine-GP model, no kidney-specific labs (AUC=0.7772).
            Ignored if model_path is provided explicitly.
        model_path : str or Path, optional
            Override: path to a specific .joblib file.
        meta_path : str or Path, optional
            Override: path to a specific _metadata.json file.
        """
        if model_path is None:
            if model_type not in _MODEL_FILES:
                raise ValueError(
                    f"model_type must be one of {list(_MODEL_FILES)}; got {model_type!r}"
                )
            model_path = MODEL_DIR / _MODEL_FILES[model_type]
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")

        model_path = pathlib.Path(model_path)
        if meta_path is None:
            meta_path = str(model_path).replace(".joblib", "_metadata.json")

        self.pipeline = joblib.load(model_path)
        with open(meta_path) as f:
            self.meta = json.load(f)

        self.model_type        = model_type
        self.BASE_FEATURES     = self.meta["base_features"]
        self.ALL_FEATURES      = self.meta["all_features"]
        self.THR_DEFAULT       = self.meta["threshold_default"]    # 0.3
        self.THR_SCREENING     = self.meta["threshold_screening"]  # 0.48 (full) / 0.25 (routine)

    # ── Public API ─────────────────────────────────────────────────────────────

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability scores (0–1) for each row."""
        return self.pipeline.predict_proba(self._prepare(X))[:, 1]

    def predict(self, X: pd.DataFrame, threshold=None) -> np.ndarray:
        """Return binary predictions (0/1).

        threshold=None uses THR_DEFAULT (0.3, high recall).
        Pass threshold=self.THR_SCREENING for the screening operating point.
        """
        thr = threshold if threshold is not None else self.THR_DEFAULT
        return (self.predict_proba(X) >= thr).astype(int)

    def score_one(self, record: dict, threshold=None) -> dict:
        """Score a single patient record (dict).

        Example:
            p.score_one({'age_years': 65, 'creatinine_serum': 1.8,
                         'blood_urea_nitrogen': 25, 'med_count': 5, ...})
        """
        X = pd.DataFrame([record])
        prob = float(self.predict_proba(X)[0])
        thr = threshold if threshold is not None else self.THR_DEFAULT
        return {
            "probability": round(prob, 4),
            "flag": int(prob >= thr),
            "threshold_used": thr,
            "screening_flag": int(prob >= self.THR_SCREENING),
        }

    def feature_importance(self) -> pd.DataFrame:
        """Return coefficient table sorted by |coefficient|."""
        coefs = self.meta["coefficients"]
        df = pd.DataFrame(list(coefs.items()), columns=["feature", "coefficient"])
        df = df.reindex(df["coefficient"].abs().sort_values(ascending=False).index)
        df["direction"] = df["coefficient"].apply(lambda x: "↑ risk" if x > 0 else "↓ risk")
        return df.reset_index(drop=True)

    def summary(self) -> None:
        """Print model card."""
        m = self.meta
        h = m["holdout_eval"]
        cv = m["cv_5fold"]
        print(f"{'='*55}")
        print(f"  {m['model_name']}  v{m['model_version']}")
        print(f"{'='*55}")
        print(f"  {m['description']}")
        print(f"  Trained on: {m['trained_on']}")
        print(f"  N total:    {m['n_train_total']}  |  N positive: {m['n_positive']}  ({m['prevalence_pct']}%)")
        print(f"  N features: {m['n_features_total']} ({len(m['base_features'])} base + {len(m['miss_flag_features'])} miss flags)")
        print()
        print(f"  ── Holdout (20% test) ──────────────────────────")
        print(f"  ROC-AUC:         {h['roc_auc']:.4f}")
        print(f"  Recall  @thr=0.3 : {h['recall_at_default_thr']:.4f}  (high-sensitivity screening)")
        print(f"  Prec    @thr=0.3 : {h['precision_at_default_thr']:.4f}")
        print(f"  Recall  @thr={m['threshold_screening']} : {h['recall_at_screening_thr']}  (≥85% recall)")
        print(f"  Prec    @thr={m['threshold_screening']} : {h['precision_at_screening_thr']}  (~1 FP per 5 referrals)")
        print()
        print(f"  ── 5-Fold CV ───────────────────────────────────")
        print(f"  CV ROC-AUC:  {cv['roc_auc_mean']:.4f} ± {cv['roc_auc_std']:.4f}")
        print(f"  CV Recall:   {cv['recall_mean']:.4f} ± {cv['recall_std']:.4f}")
        print(f"{'='*55}")
        print()
        note = m.get("eda_notes", {}).get("recommendation", "")
        if note:
            print(f"  NOTE: {note}")

    # ── Private helpers ────────────────────────────────────────────────────────

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        """Add missingness flags and reorder columns to match training layout."""
        X = X.copy()
        # Fill any missing base features with NaN
        for f in self.BASE_FEATURES:
            if f not in X.columns:
                X[f] = np.nan
        # Add miss flags
        for f in self.BASE_FEATURES:
            flag = f + "_miss"
            if flag in self.ALL_FEATURES:
                X[flag] = X[f].isnull().astype(int)
        # Reorder to exactly match training column order
        return X.reindex(columns=self.ALL_FEATURES)


if __name__ == "__main__":
    print("── Full model (52 features, labs + quest) ──────────────────")
    p_full = KidneyPredictor(model_type="full")
    p_full.summary()
    print("\nTop 10 features by |coefficient|:")
    print(p_full.feature_importance().head(10).to_string(index=False))

    # Smoke test: high-risk patient
    high_risk = {
        "age_years": 68,
        "creatinine_serum": 2.1,
        "blood_urea_nitrogen": 32,
        "uacr_mg_g": 85,
        "med_count": 7,
        "ever_told_high_bp": 1,
        "ever_told_diabetes": 1,
        "general_health_condition": 4,
    }
    result = p_full.score_one(high_risk)
    print(f"\nSmoke test — full model (high-risk patient): {result}")
    assert result["probability"] > 0.0, "predict_proba returned 0 — check pipeline"
    print("Smoke test PASSED\n")

    print("── Routine model (30 features, GP-visit only) ──────────────")
    p_routine = KidneyPredictor(model_type="routine")
    p_routine.summary()
    print("\nTop 10 features by |coefficient|:")
    print(p_routine.feature_importance().head(10).to_string(index=False))

    # Smoke test: routine-compatible record (no kidney-specific labs)
    routine_record = {
        "age_years": 68,
        "fasting_glucose": 110,
        "hdl_cholesterol": 40,
        "triglycerides": 200,
        "sbp_mean": 145,
        "dbp_mean": 88,
        "med_count": 7,
        "ever_told_high_bp": 1,
        "ever_told_diabetes": 1,
        "general_health_condition": 4,
    }
    result_r = p_routine.score_one(routine_record)
    print(f"\nSmoke test — routine model (high-risk patient): {result_r}")
    assert result_r["probability"] > 0.0, "predict_proba returned 0 — check pipeline"
    print("Smoke test PASSED")
