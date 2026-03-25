#!/usr/bin/env python3
"""
knn_scorer.py
-------------
KNN neighbourhood lab signal scorer for HalfFull.

Mirrors the interface of score_answers.py: reads a flat JSON answers dict
from stdin, returns a JSON block with neighbour lab signals to stdout.

Artifacts are loaded once at module level (not per request) so this module
can be imported and reused across calls without reloading the 7437-row index.

Usage (standalone):
    echo '{"age_years": "45", "gender": "2", ...}' | python3 scripts/knn_scorer.py

Usage (imported):
    from scripts.knn_scorer import KNNScorer
    scorer = KNNScorer()                        # loads once
    result = scorer.score(answers_dict)         # fast per-call

Output shape:
    {
      "lab_signals": [
        {
          "lab":               "Creatinine",
          "lab_col":           "serum_creatinine_mg_dl",
          "direction":         "high",
          "neighbour_pct":     43,
          "lift":              7.4,
          "ref_lower":         0.5,
          "ref_upper":         1.1,
          "context":           null
        },
        ...
      ],
      "n_signals":   5,
      "k_neighbours": 50
    }
"""

from __future__ import annotations

import json
import os
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_distances

warnings.filterwarnings("ignore")

ROOT         = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACT_DIR = ROOT / "data/processed/cluster/artifacts"

# Display names for lab columns — used in output "lab" field
LAB_DISPLAY = {
    "ferritin_ng_ml":                               "Ferritin",
    "serum_creatinine_mg_dl":                       "Creatinine",
    "serum_albumin_g_dl":                           "Albumin",
    "serum_iron_ug_dl":                             "Serum Iron",
    "tibc_ug_dl":                                   "TIBC (iron binding capacity)",
    "transferrin_saturation_pct":                   "Transferrin Saturation",
    "total_bilirubin_mg_dl":                        "Total Bilirubin",
    "total_cholesterol_mg_dl":                      "Total Cholesterol",
    "triglycerides_mg_dl":                          "Triglycerides",
    "hdl_cholesterol_mg_dl":                        "HDL Cholesterol",
    "fasting_glucose_mg_dl":                        "Fasting Glucose",
    "alt_u_l":                                      "ALT (liver enzyme)",
    "ast_u_l":                                      "AST (liver enzyme)",
    "ggt_u_l":                                      "GGT (liver enzyme)",
    "alp_u_l":                                      "ALP (alkaline phosphatase)",
    "bun_mg_dl":                                    "BUN (blood urea nitrogen)",
    "LBXHGB_hemoglobin_g_dl":                       "Hemoglobin",
    "LBXHCT_hematocrit":                            "Hematocrit",
    "LBXRBCSI_red_blood_cell_count_million_cells_ul": "RBC Count",
    "LBXMCVSI_mean_cell_volume_fl":                 "MCV (mean cell volume)",
    "LBXMCHSI_mean_cell_hemoglobin_pg":             "MCH (mean cell hemoglobin)",
    "LBXPLTSI_platelet_count_1000_cells_ul":        "Platelet Count",
    "LBXWBCSI_white_blood_cell_count_1000_cells_ul": "WBC Count",
    "LBXGH_glycohemoglobin":                        "HbA1c (glycated hemoglobin)",
    "LBXHSCRP_hs_c_reactive_protein_mg_l":          "hsCRP (high-sensitivity CRP)",
    "LBDLDL_ldl_cholesterol_friedewald_mg_dl":      "LDL Cholesterol",
    "LBXSC3SI_bicarbonate_mmol_l":                  "Bicarbonate",
    "LBXSCA_total_calcium_mg_dl":                   "Calcium",
    "LBXSKSI_potassium_mmol_l":                     "Potassium",
    "LBXSNASI_sodium_mmol_l":                       "Sodium",
    "LBXSTP_total_protein_g_dl":                    "Total Protein",
    "sbp_1":                                        "Systolic Blood Pressure",
    "dbp_1":                                        "Diastolic Blood Pressure",
}

# Columns with sex/age-free reference ranges (NaN bounds in the ref file)
SEX_MAP = {"Male": "Male", "Female": "Female", 1: "Male", 2: "Female", "1": "Male", "2": "Female"}

DUPLICATE_LAB_COLS = {
    "LBXFER_ferritin_ng_ml", "LBXSCR_creatinine_refrigerated_serum_mg_dl",
    "LBXSIR_iron_refrigerated_serum_ug_dl", "LBXIRN_iron_frozen_serum_ug_dl",
    "LBXSAL_albumin_refrigerated_serum_g_dl", "LBXSTB_total_bilirubin_mg_dl",
    "LBXTC_total_cholesterol_mg_dl", "LBDTIB_total_iron_binding_capacity_tibc_ug_dl",
    "LBXTR_triglyceride_mg_dl", "LBDPCT_transferrin_saturation",
    "LBXSAPSI_alkaline_phosphatase_alp_iu_l", "LBXSASSI_aspartate_aminotransferase_ast_u_l",
    "LBXSATSI_alanine_aminotransferase_alt_u_l", "LBXSGTSI_gamma_glutamyl_transferase_ggt_iu_l",
    "LBXGLU_fasting_glucose_mg_dl", "LBDHDD_direct_hdl_cholesterol_mg_dl",
    "dbp_2", "dbp_3", "sbp_2", "sbp_3",
}
NON_LAB_REF_COLS = {"bmi", "waist_cm"}

LAB_SPECIFIC_THRESHOLDS = {
    "alt_u_l": 0.10, "ast_u_l": 0.10,
    "ggt_u_l": 0.10, "alp_u_l": 0.10,
    "total_bilirubin_mg_dl": 0.10,
}

MIN_NEIGHBOUR_FRACTION = 0.15
MIN_LIFT               = 1.5
KNN_K                  = 50

FERRITIN_CD_COLS = {
    "serum_creatinine_mg_dl", "LBXHGB_hemoglobin_g_dl", "LBXHCT_hematocrit",
    "alt_u_l", "ast_u_l", "ggt_u_l", "LBXGH_glycohemoglobin", "fasting_glucose_mg_dl",
}


# ---------------------------------------------------------------------------
# KNNScorer — loads artifacts once, scores per call
# ---------------------------------------------------------------------------

class KNNScorer:
    def __init__(self) -> None:
        pkg_path = ARTIFACT_DIR / "knn_inference_pkg.pkl"
        pop_path = ARTIFACT_DIR / "lab_population_rates.json"

        if not pkg_path.exists():
            raise FileNotFoundError(
                f"KNN inference package not found at {pkg_path}. "
                "Run cluster_knn_inference.py first."
            )

        with open(pkg_path, "rb") as f:
            pkg = pickle.load(f)

        self.X_index      = pkg["X_index"]        # (7437, 46) normalised anchor matrix
        self.index_seqns  = pkg["index_seqns"]    # (7437,) SEQN array
        self.anchor_cols  = pkg["anchor_cols"]    # list of 46 feature names
        self.imputer      = pkg["imputer"]        # fitted SimpleImputer
        self.ref_lookup   = pkg["ref_lookup"]     # {col: [{sex, age_min, age_max, lower, upper}]}

        self.pop_rates: dict = {}
        if pop_path.exists():
            with open(pop_path) as f:
                self.pop_rates = json.load(f)

        # Lab values for all index rows — loaded from the pkl (baked in by
        # cluster_knn_inference.py) so no 20 MB CSV is needed at runtime.
        # Falls back to loading the CSV for backward compatibility with old pkls.
        if "lab_df" in pkg:
            self._final_df = pkg["lab_df"]
        else:
            final_path = ROOT / "data/processed/nhanes_merged_adults_final.csv"
            self._final_df = pd.read_csv(final_path, low_memory=False).set_index("SEQN")

        self._lab_cols = [
            c for c in self.ref_lookup
            if c in self._final_df.columns
            and c not in DUPLICATE_LAB_COLS
            and c not in NON_LAB_REF_COLS
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, answers: dict) -> dict:
        """
        Given a flat answers dict (same format as score_answers.py input),
        return a product-ready KNN lab signals block.

        answers must contain at minimum:
          - age_years  (numeric)
          - gender     (1/2 or "Male"/"Female" or "1"/"2")
        """
        sex, age = self._extract_sex_age(answers)
        user_vec = self._build_user_vector(answers)

        if user_vec is None:
            return {"lab_signals": [], "n_signals": 0, "k_neighbours": KNN_K,
                    "error": "insufficient anchor features to run KNN"}

        dists       = cosine_distances(user_vec, self.X_index)[0]
        nb_seqns    = self.index_seqns[np.argsort(dists)[:KNN_K]]
        lab_signals = self._compute_signals(nb_seqns, sex, age)

        return {
            "lab_signals":   lab_signals,
            "n_signals":     len(lab_signals),
            "k_neighbours":  KNN_K,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_sex_age(self, answers: dict) -> tuple[str, float]:
        gender_raw = answers.get("gender", "Female")
        sex = SEX_MAP.get(gender_raw, SEX_MAP.get(str(gender_raw), "Female"))
        try:
            age = float(answers.get("age_years", 40))
        except (TypeError, ValueError):
            age = 40.0
        return sex, age

    def _build_user_vector(self, answers: dict) -> np.ndarray | None:
        """Map answers dict onto anchor feature order, impute, return (1, n_features)."""
        row = []
        n_present = 0
        for col in self.anchor_cols:
            val = answers.get(col)
            if val is not None:
                try:
                    row.append(float(val))
                    n_present += 1
                except (TypeError, ValueError):
                    row.append(np.nan)
            else:
                row.append(np.nan)

        if n_present < 5:
            return None   # too few features to place user meaningfully

        arr = np.array(row, dtype=float).reshape(1, -1)
        return self.imputer.transform(arr)

    def _get_ref_range(self, col: str, sex: str, age: float):
        for e in self.ref_lookup.get(col, []):
            sex_ok    = pd.isna(e["sex"])    or e["sex"] == sex
            age_min_ok = pd.isna(e["age_min"]) or e["age_min"] <= age
            age_max_ok = pd.isna(e["age_max"]) or age <= e["age_max"]
            if sex_ok and age_min_ok and age_max_ok:
                return e["lower"], e["upper"]
        return None

    def _compute_signals(self, nb_seqns: np.ndarray, sex: str, age: float) -> list[dict]:
        extra = [c for c in ["gender", "age_years"] if c in self._final_df.columns]
        neighbours = self._final_df.loc[
            self._final_df.index.isin(nb_seqns),
            self._lab_cols + extra
        ]

        results = []
        for col in self._lab_cols:
            high, low, checked, vals = 0, 0, 0, []
            for _, row in neighbours.iterrows():
                val = row.get(col)
                if pd.isna(val):
                    continue
                nb_sex = SEX_MAP.get(row.get("gender", sex), sex)
                nb_age = row.get("age_years", age)
                ref = self._get_ref_range(col, nb_sex, nb_age)
                if ref is None:
                    ref = self._get_ref_range(col, sex, age)
                if ref is None:
                    continue
                checked += 1
                vals.append(float(val))
                if val > ref[1]:
                    high += 1
                elif val < ref[0]:
                    low += 1

            if checked == 0:
                continue

            n_abnormal = max(high, low)
            fraction   = n_abnormal / checked
            direction  = "high" if high >= low else "low"

            threshold = LAB_SPECIFIC_THRESHOLDS.get(col, MIN_NEIGHBOUR_FRACTION)
            if fraction < threshold:
                continue

            pop_rate = self.pop_rates.get(col, {}).get(direction, 0.0) / 100.0
            if pop_rate > 0:
                lift = fraction / pop_rate
                if lift < MIN_LIFT:
                    continue
            else:
                lift = None

            ref_user = self._get_ref_range(col, sex, age)

            def _clean(v):
                """Return None for NaN, otherwise the value."""
                try:
                    return None if (v is None or (isinstance(v, float) and np.isnan(v))) else v
                except Exception:
                    return None

            results.append({
                "lab":           LAB_DISPLAY.get(col, col),
                "lab_col":       col,
                "direction":     direction,
                "neighbour_pct": round(fraction * 100),
                "lift":          round(lift, 1) if lift is not None else None,
                "ref_lower":     _clean(ref_user[0]) if ref_user else None,
                "ref_upper":     _clean(ref_user[1]) if ref_user else None,
                "context":       None,
            })

        results.sort(key=lambda x: -(x["lift"] or 0))

        # Ferritin context
        surfaced_cols = {r["lab_col"] for r in results}
        for r in results:
            if r["lab_col"] == "ferritin_ng_ml" and r["direction"] == "high":
                if surfaced_cols & FERRITIN_CD_COLS:
                    r["context"] = (
                        "Elevated ferritin in this neighbourhood likely reflects "
                        "chronic inflammation or an active condition (kidney, liver, "
                        "or metabolic) rather than iron overload."
                    )
                else:
                    r["context"] = (
                        "Elevated ferritin without clear co-occurring disease signals. "
                        "Could reflect iron overload, recent illness, or subclinical "
                        "inflammation. Worth checking alongside serum iron and "
                        "transferrin saturation."
                    )

        return results


# ---------------------------------------------------------------------------
# Standalone stdin/stdout entry point
# ---------------------------------------------------------------------------

def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input received"}))
        sys.exit(1)

    try:
        answers = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON: {exc}"}))
        sys.exit(1)

    try:
        scorer = KNNScorer()
        result = scorer.score(answers)
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
