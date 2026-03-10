from pathlib import Path
from functools import reduce

import pandas as pd
import pyreadstat


RAW_DIR = Path("data/raw/nhanes")
OUTPUT_FILE = Path("data/processed/examination_clean.csv")


def read_xpt_columns(filename: str, columns: list[str]) -> pd.DataFrame:
    file_path = RAW_DIR / filename
    df, _ = pyreadstat.read_xport(file_path)

    missing_cols = [col for col in columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in {filename}: {missing_cols}")

    return df[columns].copy()


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 1) Body measures
    bmx = read_xpt_columns(
        "P_BMX.xpt",
        ["SEQN", "BMXHT", "BMXWT", "BMXBMI", "BMXWAIST", "BMXHIP"],
    )

    # 2) Blood pressure
    bpxo = read_xpt_columns(
        "P_BPXO.xpt",
        [
            "SEQN",
            "BPXOSY1", "BPXOSY2", "BPXOSY3",
            "BPXODI1", "BPXODI2", "BPXODI3",
            "BPXOPLS1", "BPXOPLS2", "BPXOPLS3",
        ],
    )

    # 3) Liver elastography
    lux = read_xpt_columns(
        "P_LUX.xpt",
        ["SEQN", "LUXCAPM", "LUXSMED", "LUAXSTAT", "LUANMVGP", "LUXSIQRM"],
    )

    # 4) Oral health recommendation
    ohxref = read_xpt_columns(
        "P_OHXREF.xpt",
        ["SEQN", "OHAROCGP", "OHAROCDT", "OHAROCOH"],
    )

    # 5) Oral health dentition
    ohxden = read_xpt_columns(
        "P_OHXDEN.xpt",
        ["SEQN", "OHXIMP", "OHXRCAR", "OHXRRES"],
    )

    # Merge all exam files on SEQN
    dfs = [bmx, bpxo, lux, ohxref, ohxden]
    exam_df = reduce(lambda left, right: pd.merge(left, right, on="SEQN", how="outer"), dfs)

    # Transform SEQN into integers
    exam_df["SEQN"] = exam_df["SEQN"].astype("Int64")

    # Rename columns to readable names
    exam_df = exam_df.rename(
        columns={
            "BMXHT": "height_cm",
            "BMXWT": "weight_kg",
            "BMXBMI": "bmi",
            "BMXWAIST": "waist_cm",
            "BMXHIP": "hip_cm",

            "BPXOSY1": "sbp_1",
            "BPXOSY2": "sbp_2",
            "BPXOSY3": "sbp_3",
            "BPXODI1": "dbp_1",
            "BPXODI2": "dbp_2",
            "BPXODI3": "dbp_3",
            "BPXOPLS1": "pulse_1",
            "BPXOPLS2": "pulse_2",
            "BPXOPLS3": "pulse_3",

            "LUXCAPM": "liver_cap_dbm",
            "LUXSMED": "liver_stiffness_kpa",
            "LUAXSTAT": "liver_exam_status",
            "LUANMVGP": "liver_valid_measures",
            "LUXSIQRM": "liver_stiffness_iqr_ratio",

            "OHAROCGP": "oral_gum_problem_yesno",
            "OHAROCDT": "oral_decayed_teeth_yesno",
            "OHAROCOH": "oral_hygiene_issue_yesno",
            "OHXIMP": "any_implant",
            "OHXRCAR": "any_root_caries",
            "OHXRRES": "any_root_restoration_caries",
        }
    )

    # Keep one row per participant
    exam_df = exam_df.drop_duplicates(subset="SEQN")

    # Sort and reset row index
    exam_df = exam_df.sort_values("SEQN").reset_index(drop=True)

    # Quality checks
    print("Shape:", exam_df.shape)
    print("Unique participants:", exam_df["SEQN"].nunique())
    print("\nMissing values:")
    print(exam_df.isna().sum())
    print("\nPreview:")
    print(exam_df.head())

    exam_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nClean examination dataset saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()