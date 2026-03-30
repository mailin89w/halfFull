"""
generate_calibration_plots.py
------------------------------
ML-05: Generate reliability diagrams (calibration plots) for the three
retrained models. Saves to ml-05-retraining/eval/.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

ROOT      = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models_normalized"
EVAL_DIR  = Path(__file__).resolve().parent / "eval"
DATA_PATH = ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"

EVAL_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

SEED = 42

_EDU_ORDER = {
    "Less than 9th grade":       0,
    "9-11th grade":              1,
    "High school / GED":         2,
    "Some college / AA":         3,
    "College graduate or above": 4,
}


def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["gender_female"] = np.where(df["gender"].eq("Female"), 1.0,
                          np.where(df["gender"].isna(), np.nan, 0.0))
    if "education" in df.columns and "education_ord" not in df.columns:
        df["education_ord"] = df["education"].map(_EDU_ORDER)
    if "pregnancy_status_bin" not in df.columns:
        df["pregnancy_status_bin"] = np.where(
            df["pregnancy_status"].eq("Yes, pregnant"), 1.0, 0.0
        )
    # waist flags (inflammation)
    waist = df["waist_cm"].fillna(0.0)
    is_female = df["gender_female"].fillna(0.0)
    df["waist_elevated_female"] = ((is_female == 1) & (waist >= 0.35)).astype(float)
    df["waist_elevated_male"]   = ((is_female == 0) & (waist >= 0.65)).astype(float)
    # bmi x family dm (prediabetes)
    bmi    = df.get("bmi", pd.Series(np.nan, index=df.index))
    fam_dm = df.get("mcq300c___close_relative_had_diabetes", pd.Series(np.nan, index=df.index))
    fam_dm_bin = fam_dm.apply(
        lambda v: 1.0 if (not pd.isna(v) and int(v) == 1) else 0.0 if not pd.isna(v) else 0.0
    )
    df["bmi_x_family_dm"] = bmi.fillna(0.0) * fam_dm_bin
    return df


def plot_calibration(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    model_name: str,
    n_bins: int = 10,
    save_path: Path | None = None,
) -> None:
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Reliability diagram
    ax = axes[0]
    ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
    ax.plot(prob_pred, prob_true, "o-", color="#2196F3", label=f"{model_name}")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(f"Reliability Diagram — {model_name}")
    ax.legend()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)

    # Score histogram
    ax2 = axes[1]
    ax2.hist(y_prob[y_true == 0], bins=30, alpha=0.5, label="Negative", color="#F44336")
    ax2.hist(y_prob[y_true == 1], bins=30, alpha=0.5, label="Positive", color="#4CAF50")
    ax2.set_xlabel("Predicted probability")
    ax2.set_ylabel("Count")
    ax2.set_title(f"Score Distribution — {model_name}")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Saved calibration plot → {save_path}")
    plt.close()


def main():
    print("=" * 60)
    print("  Calibration Plots — ML-05")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH, low_memory=False)
    df = prepare_df(df)
    print(f"Loaded: {df.shape[0]:,} rows")

    # ── Kidney v3 ───────────────────────────────────────────────────────────────
    print("\n── Kidney v3 ─────────────────────────────────────────────────────────")
    k_meta   = json.loads((MODELS_DIR / "kidney_lr_v3_hard_neg_metadata.json").read_text())
    k_pipe   = joblib.load(MODELS_DIR / "kidney_lr_v3_hard_neg.joblib")
    k_feats  = k_meta["features"]
    k_target = "kidney"
    y_k   = df[k_target].fillna(0).astype(int)
    prob_k = k_pipe.predict_proba(df[k_feats])[:, 1]
    plot_calibration(
        y_k.values, prob_k, "Kidney v3 (hard-neg)",
        save_path=EVAL_DIR / "calibration_kidney_v3.png"
    )

    # ── Inflammation v4 ─────────────────────────────────────────────────────────
    print("\n── Inflammation v4 ───────────────────────────────────────────────────")
    i_meta   = json.loads((MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg_metadata.json").read_text())
    i_pipe   = joblib.load(MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg.joblib")
    i_feats  = i_meta["features"]
    i_target = "hidden_inflammation"
    y_i   = df[i_target].fillna(0).astype(int)
    prob_i = i_pipe.predict_proba(df[i_feats])[:, 1]
    plot_calibration(
        y_i.values, prob_i, "Inflammation v4 (hard-neg)",
        save_path=EVAL_DIR / "calibration_inflammation_v4.png"
    )

    # ── Prediabetes v3 ──────────────────────────────────────────────────────────
    print("\n── Prediabetes v3 ────────────────────────────────────────────────────")
    p_meta   = json.loads((MODELS_DIR / "prediabetes_xgb_v3_hard_neg_metadata.json").read_text())
    p_pipe   = joblib.load(MODELS_DIR / "prediabetes_xgb_v3_hard_neg.joblib")
    p_feats  = p_meta["features"]
    p_target = "prediabetes"
    y_p   = df[p_target].fillna(0).astype(int)
    prob_p = p_pipe.predict_proba(df[p_feats])[:, 1]
    plot_calibration(
        y_p.values, prob_p, "Prediabetes v3 (hard-neg)",
        save_path=EVAL_DIR / "calibration_prediabetes_v3.png"
    )

    print("\nAll calibration plots saved to:", EVAL_DIR)


if __name__ == "__main__":
    main()
