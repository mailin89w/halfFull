from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "nhanes"
OUTPUT_FILE = ROOT / "data" / "processed" / "nhanes_2017_2018_vitd_real_cohort.csv"
SUMMARY_FILE = ROOT / "data" / "processed" / "nhanes_2017_2018_vitd_summary.json"


def read_xpt(name: str, keep: list[str]) -> pd.DataFrame:
    df = pd.read_sas(RAW_DIR / f"{name}.xpt", format="xport", encoding="latin1")
    cols = [c for c in keep if c in df.columns]
    out = df[cols].copy()
    out["SEQN"] = pd.to_numeric(out["SEQN"], errors="coerce").astype("Int64")
    return out


def aggregate_rx(df: pd.DataFrame) -> pd.DataFrame:
    rxduse = pd.to_numeric(df["RXDUSE"], errors="coerce")
    rxdcount = pd.to_numeric(df["RXDCOUNT"], errors="coerce")
    drug = df["RXDDRUG"].astype("string").str.strip()
    med_row = rxduse.eq(1) & drug.notna() & drug.ne("")

    med_count = (
        pd.DataFrame({"SEQN": df["SEQN"], "_med_count": rxdcount.where(med_row)})
        .groupby("SEQN", as_index=False)["_med_count"]
        .max()
        .rename(columns={"_med_count": "med_count"})
    )
    fallback = (
        pd.DataFrame({"SEQN": df.loc[med_row, "SEQN"]})
        .groupby("SEQN", as_index=False)
        .size()
        .rename(columns={"size": "_fallback_med_count"})
    )
    med_count = med_count.merge(fallback, on="SEQN", how="outer")
    med_count["med_count"] = med_count["med_count"].fillna(med_count["_fallback_med_count"]).fillna(0)
    med_count = med_count[["SEQN", "med_count"]]

    disease_list = (
        pd.DataFrame({"SEQN": df.loc[med_row, "SEQN"], "drug": drug.loc[med_row]})
        .drop_duplicates(subset=["SEQN", "drug"])
        .groupby("SEQN", as_index=False)["drug"]
        .agg(lambda vals: ", ".join(sorted(vals)))
        .rename(columns={"drug": "rxd_disease_list"})
    )
    return med_count.merge(disease_list, on="SEQN", how="left")


def main() -> None:
    demo = read_xpt("DEMO_J", ["SEQN", "RIAGENDR", "RIDAGEYR", "RIDEXPRG", "DMDEDUC2"])
    alq = read_xpt("ALQ_J", ["SEQN", "ALQ130"])
    bpq = read_xpt("BPQ_J", ["SEQN", "BPQ020", "BPQ080"])
    cdq = read_xpt("CDQ_J", ["SEQN", "CDQ010"])
    diq = read_xpt("DIQ_J", ["SEQN", "DIQ010", "DIQ050", "DIQ070"])
    dpq = read_xpt("DPQ_J", ["SEQN", "DPQ040"])
    huq = read_xpt("HUQ_J", ["SEQN", "HUQ010", "HUQ071"])
    kiq = read_xpt("KIQ_U_J", ["SEQN", "KIQ005", "KIQ022", "KIQ042", "KIQ044", "KIQ480"])
    mcq = read_xpt("MCQ_J", ["SEQN", "MCQ053", "MCQ080", "MCQ092", "MCQ160A", "MCQ160B", "MCQ160L", "MCQ300C"])
    rhq = read_xpt("RHQ_J", ["SEQN", "RHQ031", "RHQ060", "RHQ131", "RHQ540"])
    slq = read_xpt("SLQ_J", ["SEQN", "SLQ030", "SLQ050"])
    smq = read_xpt("SMQ_J", ["SEQN", "SMQ040"])
    whq = read_xpt("WHQ_J", ["SEQN", "WHQ040", "WHQ070"])
    ocq = read_xpt("OCQ_J", ["SEQN", "OCQ180"])
    bmx = read_xpt("BMX_J", ["SEQN", "BMXWT", "BMXBMI"])
    cbc = read_xpt("CBC_J", ["SEQN", "LBXWBCSI"])
    biopro = read_xpt("BIOPRO_J", ["SEQN", "LBXSTP"])
    vid = read_xpt("VID_J", ["SEQN", "LBXVIDMS"])
    rx = read_xpt("RXQ_RX_J", ["SEQN", "RXDUSE", "RXDDRUG", "RXDCOUNT"])
    rx_agg = aggregate_rx(rx)

    merged = demo.copy()
    for frame in [
        alq, bpq, cdq, diq, dpq, huq, kiq, mcq, rhq, slq, smq, whq, ocq,
        bmx, cbc, biopro, vid, rx_agg,
    ]:
        merged = merged.merge(frame, on="SEQN", how="left")

    out = pd.DataFrame({
        "SEQN": merged["SEQN"],
        "gender_code": pd.to_numeric(merged["RIAGENDR"], errors="coerce"),
        "age_years": pd.to_numeric(merged["RIDAGEYR"], errors="coerce"),
        "pregnancy_status_code": pd.to_numeric(merged["RIDEXPRG"], errors="coerce"),
        "education_code": pd.to_numeric(merged["DMDEDUC2"], errors="coerce"),
        "alq130_avg_drinks_per_day": pd.to_numeric(merged["ALQ130"], errors="coerce"),
        "bpq020_high_bp": pd.to_numeric(merged["BPQ020"], errors="coerce"),
        "bpq080_high_cholesterol": pd.to_numeric(merged["BPQ080"], errors="coerce"),
        "cdq010_sob_stairs": pd.to_numeric(merged["CDQ010"], errors="coerce"),
        "diq010_diabetes": pd.to_numeric(merged["DIQ010"], errors="coerce"),
        "diq050_insulin": pd.to_numeric(merged["DIQ050"], errors="coerce"),
        "diq070_diabetes_pills": pd.to_numeric(merged["DIQ070"], errors="coerce"),
        "dpq040_fatigue": pd.to_numeric(merged["DPQ040"], errors="coerce"),
        "huq010_general_health": pd.to_numeric(merged["HUQ010"], errors="coerce"),
        "huq071_hospital": pd.to_numeric(merged["HUQ071"], errors="coerce"),
        "kiq005_urinary_leakage_freq": pd.to_numeric(merged["KIQ005"], errors="coerce"),
        "kiq022_weak_kidneys": pd.to_numeric(merged["KIQ022"], errors="coerce"),
        "kiq042_leak_exertion": pd.to_numeric(merged["KIQ042"], errors="coerce"),
        "kiq044_urge_incontinence": pd.to_numeric(merged["KIQ044"], errors="coerce"),
        "kiq480_nocturia": pd.to_numeric(merged["KIQ480"], errors="coerce"),
        "mcq053_anemia_treatment": pd.to_numeric(merged["MCQ053"], errors="coerce"),
        "mcq080_overweight_dx": pd.to_numeric(merged["MCQ080"], errors="coerce"),
        "mcq092_transfusion": pd.to_numeric(merged["MCQ092"], errors="coerce"),
        "mcq160a_arthritis": pd.to_numeric(merged["MCQ160A"], errors="coerce"),
        "mcq160b_heart_failure": pd.to_numeric(merged["MCQ160B"], errors="coerce"),
        "mcq160l_liver_condition": pd.to_numeric(merged["MCQ160L"], errors="coerce"),
        "mcq300c_family_diabetes": pd.to_numeric(merged["MCQ300C"], errors="coerce"),
        "med_count": pd.to_numeric(merged["med_count"], errors="coerce"),
        "ocq180_hours_worked_week": pd.to_numeric(merged["OCQ180"], errors="coerce"),
        "rhq031_regular_periods": pd.to_numeric(merged["RHQ031"], errors="coerce"),
        "rhq060_age_last_period": pd.to_numeric(merged["RHQ060"], errors="coerce"),
        "rhq131_ever_pregnant": pd.to_numeric(merged["RHQ131"], errors="coerce"),
        "rhq540_hormone_use": pd.to_numeric(merged["RHQ540"], errors="coerce"),
        "slq030_snore_freq": pd.to_numeric(merged["SLQ030"], errors="coerce"),
        "slq050_sleep_trouble_doctor": pd.to_numeric(merged["SLQ050"], errors="coerce"),
        "smq040_smoke_now": pd.to_numeric(merged["SMQ040"], errors="coerce"),
        "total_protein_g_dl": pd.to_numeric(merged["LBXSTP"], errors="coerce"),
        "wbc_1000_cells_ul": pd.to_numeric(merged["LBXWBCSI"], errors="coerce"),
        "weight_kg": pd.to_numeric(merged["BMXWT"], errors="coerce"),
        "bmi": pd.to_numeric(merged["BMXBMI"], errors="coerce"),
        "whq040_weight_preference": pd.to_numeric(merged["WHQ040"], errors="coerce"),
        "whq070_tried_to_lose_weight": pd.to_numeric(merged["WHQ070"], errors="coerce"),
        "vitamin_d_25oh_nmol_l": pd.to_numeric(merged["LBXVIDMS"], errors="coerce"),
        "rxd_disease_list": merged.get("rxd_disease_list"),
    })

    out["gender"] = out["gender_code"].map({1: "Male", 2: "Female"})
    out["vitamin_d_deficiency"] = (
        out["vitamin_d_25oh_nmol_l"].lt(50).where(out["vitamin_d_25oh_nmol_l"].notna())
    ).astype("float")

    out = out.drop_duplicates(subset="SEQN").sort_values("SEQN").reset_index(drop=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    summary = {
        "rows": int(len(out)),
        "unique_seqn": int(out["SEQN"].nunique()),
        "vitamin_d_non_null": int(out["vitamin_d_25oh_nmol_l"].notna().sum()),
        "vitamin_d_deficient": int(out["vitamin_d_deficiency"].fillna(0).sum()),
        "prevalence": float(out["vitamin_d_deficiency"].mean()),
    }
    SUMMARY_FILE.write_text(pd.Series(summary).to_json(indent=2), encoding="utf-8")

    print(f"Saved cohort to {OUTPUT_FILE}")
    print(summary)


if __name__ == "__main__":
    main()
