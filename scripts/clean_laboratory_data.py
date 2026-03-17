from pathlib import Path
from functools import reduce

import pandas as pd
import pyreadstat


RAW_DIR = Path("data/raw/nhanes")
OUTPUT_FILE = Path("data/processed/laboratory_clean.csv")


def read_xpt_columns(filename: str, columns: list[str]) -> pd.DataFrame:
    file_path = RAW_DIR / filename

    try:
        # First try pyreadstat
        df, _ = pyreadstat.read_xport(file_path, encoding="LATIN1")
    except UnicodeDecodeError as e:
        print(f"[WARN] pyreadstat failed for {filename}: {e}")
        print(f"[WARN] Falling back to pandas.read_sas for {filename}")

        # Fallback: pandas can read SAS XPORT directly
        df = pd.read_sas(file_path, format="xport", encoding="latin1")

        # In some cases pandas may return byte column names
        df.columns = [
            col.decode("latin1") if isinstance(col, bytes) else col
            for col in df.columns
        ]

    missing_cols = [col for col in columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in {filename}: {missing_cols}")

    return df[columns].copy()

def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 1) Fasting questionnaire
    fastqx = read_xpt_columns(
        "P_FASTQX.xpt",
        ["SEQN", "PHAFSTHR", "PHAFSTMN"],
    )

    # 2) Fasting glucose
    glu = read_xpt_columns(
        "P_GLU.xpt",
        ["SEQN", "LBXGLU"],
    )

    # 3) Insulin
    ins = read_xpt_columns(
        "P_INS.xpt",
        ["SEQN", "LBXIN"],
    )

    # 4) Total cholesterol
    tchol = read_xpt_columns(
        "P_TCHOL.xpt",
        ["SEQN", "LBXTC"],
    )

    # 5) HDL
    hdl = read_xpt_columns(
        "P_HDL.xpt",
        ["SEQN", "LBDHDD"],
    )

    # 6) Triglycerides
    trigly = read_xpt_columns(
        "P_TRIGLY.xpt",
        ["SEQN", "LBXTR"],
    )

    # 7) Ferritin
    fertin = read_xpt_columns(
        "P_FERTIN.xpt",
        ["SEQN", "LBXFER"],
    )

    # 8) Iron status
    fetib = read_xpt_columns(
        "P_FETIB.xpt",
        ["SEQN", "LBXIRN", "LBDTIB", "LBDPCT"],
    )

    # 9) Transferrin receptor
    tfr = read_xpt_columns(
        "P_TFR.xpt",
        ["SEQN", "LBXTFR"],
    )

    # 10) Urine albumin/creatinine
    alb_cr = read_xpt_columns(
        "P_ALB_CR.xpt",
        ["SEQN", "URDACT"],
    )

    # 11) Standard biochemistry
    biopro = read_xpt_columns(
        "P_BIOPRO.xpt",
        [
            "SEQN",
            "LBXSCR",
            "LBXSBU",
            "LBXSATSI",
            "LBXSASSI",
            "LBXSGTSI",
            "LBXSAPSI",
            "LBXSTB",
            "LBXSAL",
        ],
    )

    dfs = [fastqx, glu, ins, tchol, hdl, trigly, fertin, fetib, tfr, alb_cr, biopro]
    lab_df = reduce(lambda left, right: pd.merge(left, right, on="SEQN", how="outer"), dfs)

    # Transform SEQN into integers
    lab_df["SEQN"] = lab_df["SEQN"].astype("Int64")


    # Rename columns
    lab_df = lab_df.rename(
        columns={
            "PHAFSTHR": "fasting_hours_part",
            "PHAFSTMN": "fasting_minutes_part",
            "LBXGLU": "fasting_glucose_mg_dl",
            "LBXIN": "insulin_uU_ml",
            "LBXTC": "total_cholesterol_mg_dl",
            "LBDHDD": "hdl_cholesterol_mg_dl",
            "LBXTR": "triglycerides_mg_dl",
            "LBXFER": "ferritin_ng_ml",
            "LBXIRN": "serum_iron_ug_dl",
            "LBDTIB": "tibc_ug_dl",
            "LBDPCT": "transferrin_saturation_pct",
            "LBXTFR": "transferrin_receptor_mg_l",
            "URDACT": "uacr_mg_g",
            "LBXSCR": "serum_creatinine_mg_dl",
            "LBXSBU": "bun_mg_dl",
            "LBXSATSI": "alt_u_l",
            "LBXSASSI": "ast_u_l",
            "LBXSGTSI": "ggt_u_l",
            "LBXSAPSI": "alp_u_l",
            "LBXSTB": "total_bilirubin_mg_dl",
            "LBXSAL": "serum_albumin_g_dl",
        }
    )

    # Keep one row per participant
    lab_df = lab_df.drop_duplicates(subset="SEQN")

    # Sort and reset row index
    lab_df = lab_df.sort_values("SEQN").reset_index(drop=True)

    # Quality checks
    print("Shape:", lab_df.shape)
    print("Unique participants:", lab_df["SEQN"].nunique())
    print("\nMissing values:")
    print(lab_df.isna().sum())
    print("\nPreview:")
    print(lab_df.head())

    lab_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nClean laboratory dataset saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()