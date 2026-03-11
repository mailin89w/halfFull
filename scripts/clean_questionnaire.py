from pathlib import Path
from functools import reduce
import re

import pandas as pd
import pyreadstat


DATA_DIR = Path("data/raw/nhanes")
QUEST_DICT_FILE = DATA_DIR / "quest_dict.csv"
OUTPUT_FILE = Path("data/processed/merged_questionnaire.csv")

XPT_FILES = [
    "P_ALQ",
    "P_BPQ",
    "P_CDQ",
    "P_DIQ",
    "P_DPQ",
    "P_HEQ",
    "P_HUQ",
    "P_KIQ_U",
    "P_MCQ",
    "P_PAQ",
    "P_RHQ",
    "P_RXQ_RX",
    "P_SLQ",
    "P_SMQ",
    "P_WHQ",
    "P_OCQ",
    "RXQ_DRUG",
]

QUESTIONNAIRE_FILES_TO_MERGE = [
    "P_ALQ",
    "P_BPQ",
    "P_CDQ",
    "P_DIQ",
    "P_DPQ",
    "P_HEQ",
    "P_HUQ",
    "P_KIQ_U",
    "P_MCQ",
    "P_PAQ",
    "P_RHQ",
    "P_RXQ_RX",
    "P_SLQ",
    "P_SMQ",
    "P_WHQ",
    "P_OCQ",
]

MANUAL_MAPPING = {
    # Depression (PHQ-9)
    "dpq010": "dpq010___little_interest_in_doing_things",
    "dpq020": "dpq020___feeling_down_depressed_or_hopeless",
    "dpq030": "dpq030___trouble_sleeping_or_sleeping_too_much",
    "dpq040": "dpq040___feeling_tired_or_having_little_energy",
    "dpq050": "dpq050___poor_appetite_or_overeating",
    "dpq060": "dpq060___feeling_bad_about_yourself",
    "dpq070": "dpq070___trouble_concentrating_on_things",
    "dpq080": "dpq080___moving_or_speaking_slowly_or_too_fast",
    "dpq090": "dpq090___thoughts_you_would_be_better_off_dead",
    "dpq100": "dpq100___difficulty_these_problems_have_caused",
    # Medical conditions
    "mcq160a": "mcq160a___ever_told_you_had_arthritis",
    "mcq160b": "mcq160b___ever_told_you_had_congestive_heart_failure",
    "mcq160c": "mcq160c___ever_told_you_had_coronary_heart_disease",
    "mcq160d": "mcq160d___ever_told_you_had_angina",
    "mcq160e": "mcq160e___ever_told_you_had_heart_attack",
    "mcq160f": "mcq160f___ever_told_you_had_stroke",
    "mcq160l": "mcq160l___ever_told_you_had_any_liver_condition",
    "mcq160m": "mcq160m___ever_told_you_had_thyroid_problem",
    "mcq160p": "mcq160p___ever_told_you_had_copd_emphysema",
    "mcq170l": "mcq170l___still_have_liver_condition",
    "mcq170m": "mcq170m___still_have_thyroid_problem",
    "mcd180b": "mcd180b___age_when_told_you_had_chf",
    "mcd180c": "mcd180c___age_when_told_you_had_chd",
    "mcd180d": "mcd180d___age_when_told_you_had_angina",
    "mcd180e": "mcd180e___age_when_told_you_had_heart_attack",
    "mcd180l": "mcd180l___age_when_told_you_had_liver_condition",
    # Liver conditions
    "mcq510a": "mcq510a___liver_condition_fatty_liver",
    "mcq510b": "mcq510b___liver_condition_non_alcoholic_fatty_liver",
    "mcq510c": "mcq510c___liver_condition_alcoholic_liver_disease",
    "mcq510d": "mcq510d___liver_condition_hepatitis",
    "mcq510e": "mcq510e___liver_condition_autoimmune",
    "mcq510f": "mcq510f___liver_condition_other",
    # Cancer types
    "mcq230a": "mcq230a___what_kind_of_cancer_first_mention",
    "mcq230b": "mcq230b___what_kind_of_cancer_second_mention",
    "mcq230c": "mcq230c___what_kind_of_cancer_third_mention",
    "mcq230d": "mcq230d___what_kind_of_cancer_fourth_mention",
    # Family history
    "mcq300a": "mcq300a___close_relative_had_heart_attack",
    "mcq300b": "mcq300b___close_relative_had_asthma",
    "mcq300c": "mcq300c___close_relative_had_diabetes",
    # Doctor recommendations
    "mcq366a": "mcq366a___doctor_told_to_control_weight",
    "mcq366b": "mcq366b___doctor_told_to_increase_exercise",
    "mcq366c": "mcq366c___doctor_told_to_reduce_salt",
    "mcq366d": "mcq366d___doctor_told_to_reduce_fat_in_diet",
    "mcq371a": "mcq371a___doing_controlling_weight",
    "mcq371b": "mcq371b___doing_increasing_exercise",
    "mcq371c": "mcq371c___doing_reducing_salt",
    "mcq371d": "mcq371d___doing_reducing_fat_in_diet",
}

COLUMNS_TO_DROP = [
    "rhd018_x",
    "rhd018_y",
    "mcq230d___what_kind_of_cancer_fourth_mention",
    "rhq542d___other_form_of_female_hormone_used",
    "cdq009h___pain_in_epigastric_area",
]


def load_xpt_files(data_dir: Path, file_names: list[str]) -> dict[str, pd.DataFrame]:
    """Load NHANES XPT files into a dictionary of DataFrames."""
    datasets: dict[str, pd.DataFrame] = {}

    for name in file_names:
        filepath = data_dir / f"{name}.xpt"
        df, _ = pyreadstat.read_xport(filepath)
        datasets[name] = df
        print(f"Loaded {name}: {df.shape}")

    return datasets


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names to lowercase snake_case."""
    df = df.copy()
    df.columns = (
        df.columns.str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    return df


def rename_columns_with_dictionary(df: pd.DataFrame, quest_dict_file: Path) -> pd.DataFrame:
    """Rename columns using quest_dict.csv."""
    quest_dict = pd.read_csv(quest_dict_file)
    col_mapping = dict(zip(quest_dict["code"], quest_dict["code and name"]))

    df = df.copy()
    df = df.rename(columns=col_mapping)
    df = normalize_column_names(df)

    return df


def find_seqn_column(df: pd.DataFrame) -> str:
    """Find the respondent ID column after renaming."""
    seqn_candidates = [col for col in df.columns if "seqn" in col]
    if not seqn_candidates:
        raise ValueError("Could not find SEQN column in merged dataset.")
    return seqn_candidates[0]


def add_manual_column_names(df: pd.DataFrame, manual_mapping: dict[str, str]) -> pd.DataFrame:
    """Apply manual fixes for columns not mapped by quest_dict."""
    df = df.copy()
    df = df.rename(columns=manual_mapping)
    return df


def report_unmapped_columns(df: pd.DataFrame) -> None:
    """Print columns that still look like raw coded names."""
    unmapped = [col for col in df.columns if re.match(r"^[a-z]{2,4}\d+[a-z]?$", col)]
    print(f"\nUnmapped coded columns: {len(unmapped)}")
    if unmapped:
        print(unmapped)


def add_medication_columns(
    merged_df: pd.DataFrame,
    rx_df: pd.DataFrame,
    seqn_col: str,
) -> pd.DataFrame:
    """Pivot medication names wide and merge back to one row per participant."""
    rx_df = rx_df.copy()

    if "SEQN" not in rx_df.columns or "RXDDRUG" not in rx_df.columns:
        raise ValueError("P_RXQ_RX must contain SEQN and RXDDRUG columns.")

    rx_df["drug_rank"] = rx_df.groupby("SEQN").cumcount() + 1

    rx_wide = rx_df.pivot(index="SEQN", columns="drug_rank", values="RXDDRUG")
    rx_wide.columns = [f"medication_{i}" for i in rx_wide.columns]
    rx_wide = rx_wide.reset_index()

    merged_df = merged_df.merge(rx_wide, left_on=seqn_col, right_on="SEQN", how="left")

    if "SEQN_y" in merged_df.columns:
        merged_df = merged_df.drop(columns=["SEQN_y"])
    if "SEQN_x" in merged_df.columns:
        merged_df = merged_df.rename(columns={"SEQN_x": "SEQN"})

    return merged_df


def add_medication_count(df: pd.DataFrame) -> pd.DataFrame:
    """Count non-null medication columns for each participant."""
    df = df.copy()
    med_cols = [col for col in df.columns if col.startswith("medication_")]
    if med_cols:
        df["med_count"] = df[med_cols].notna().sum(axis=1)
    else:
        df["med_count"] = 0
    return df


def add_missingness_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Add row-level missingness features."""
    df = df.copy()
    df["nan_count"] = df.isnull().sum(axis=1)

    bins = [0, 50, 100, 150, 200, 250, df.shape[1]]
    labels = ["0-50", "51-100", "101-150", "151-200", "201-250", "250+"]

    # Ensure unique increasing bins
    bins = sorted(set(bins))
    if len(bins) > 1:
        valid_labels = labels[: len(bins) - 1]
        df["nan_group"] = pd.cut(df["nan_count"], bins=bins, labels=valid_labels, include_lowest=True)

    return df


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load raw NHANES files
    datasets = load_xpt_files(DATA_DIR, XPT_FILES)

    # Merge questionnaire files on SEQN
    dfs_to_merge = [datasets[name] for name in QUESTIONNAIRE_FILES_TO_MERGE]
    merged = reduce(lambda left, right: left.merge(right, on="SEQN", how="outer"), dfs_to_merge)

    print(f"\nMerged raw shape: {merged.shape}")

    # Rename columns using dictionary + normalize names
    merged = rename_columns_with_dictionary(merged, QUEST_DICT_FILE)

    # Apply manual mapping for columns not covered by dictionary
    merged = add_manual_column_names(merged, MANUAL_MAPPING)
    report_unmapped_columns(merged)

    # Drop unnecessary columns if present
    existing_drop_cols = [col for col in COLUMNS_TO_DROP if col in merged.columns]
    if existing_drop_cols:
        merged = merged.drop(columns=existing_drop_cols)

    # Find participant ID column after renaming
    seqn_col = find_seqn_column(merged)

    # Add wide medication columns from prescription data
    merged = add_medication_columns(
        merged_df=merged,
        rx_df=datasets["P_RXQ_RX"],
        seqn_col=seqn_col,
    )

    # Drop duplicate participants
    print(f"\nDuplicate rows before cleaning: {merged.duplicated().sum()}")
    print(f"Duplicate participant IDs before cleaning: {merged[seqn_col].duplicated().sum()}")

    merged = merged.drop_duplicates(subset=[seqn_col], keep="first")

    # Add simple derived features
    merged = add_medication_count(merged)
    merged = add_missingness_summary(merged)

    # Convert participant ID to nullable integer when possible
    try:
        merged[seqn_col] = merged[seqn_col].astype("Int64")
    except Exception:
        print(f"Warning: could not convert {seqn_col} to Int64.")

    # Quality checks
    print(f"\nFinal shape: {merged.shape}")
    print(f"Unique participants: {merged[seqn_col].nunique()}")
    print(f"Duplicate participant IDs remaining: {merged[seqn_col].duplicated().sum()}")

    print("\nTop missing values:")
    missing = merged.isnull().sum()
    missing_pct = (missing / len(merged) * 100).round(2)
    missing_df = pd.DataFrame({"missing": missing, "pct": missing_pct})
    print(missing_df[missing_df["missing"] > 0].sort_values("pct", ascending=False).head(20))

    med_cols = [col for col in merged.columns if col.startswith("medication_")]
    print(f"\nNumber of medication columns: {len(med_cols)}")

    if "med_count" in merged.columns:
        print("\nMedication count distribution:")
        print(merged["med_count"].value_counts().sort_index())

    if "nan_group" in merged.columns:
        print("\nMissingness group distribution:")
        print(merged["nan_group"].value_counts().sort_index())

    print("\nPreview:")
    print(merged.head())

    # Save cleaned dataset
    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"\nClean merged dataset saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()