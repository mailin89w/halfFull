from pathlib import Path
from functools import reduce
import pandas as pd
import pyreadstat

RAW_DIR = Path("data/raw/nhanes/lab")
OUTPUT_FILE = Path("data/processed/laboratory_all_clean.csv")


def read_xpt_file(file_path: Path) -> pd.DataFrame:
    """
    Read a NHANES XPT file robustly and ensure SEQN exists.
    """
    try:
        df, _ = pyreadstat.read_xport(file_path, encoding="LATIN1")
    except UnicodeDecodeError:
        df = pd.read_sas(file_path, format="xport", encoding="latin1")
        df.columns = [
            col.decode("latin1") if isinstance(col, bytes) else col
            for col in df.columns
        ]

    if "SEQN" not in df.columns:
        raise ValueError(f"SEQN missing in file: {file_path.name}")

    return df.copy()


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Raw lab directory not found: {RAW_DIR}")

    # load all NHANES lab xpt files in this folder
    lab_files = sorted(RAW_DIR.glob("*.xpt"))

    if not lab_files:
        raise FileNotFoundError(f"No .xpt files found in {RAW_DIR}")

    print(f"Found {len(lab_files)} lab files in {RAW_DIR}")

    dfs = []
    seen_cols = set()
    file_summary = []

    for file_path in lab_files:
        df = read_xpt_file(file_path)

        original_cols = df.columns.tolist()
        rename_map = {}

        # avoid collisions for non-SEQN columns
        for col in original_cols:
            if col == "SEQN":
                continue
            if col in seen_cols:
                rename_map[col] = f"{col}__{file_path.stem.lower()}"
            seen_cols.add(col)

        if rename_map:
            df = df.rename(columns=rename_map)

        file_summary.append({
            "file": file_path.name,
            "n_rows": len(df),
            "n_cols": df.shape[1],
            "seqn_unique": df["SEQN"].nunique()
        })

        print(f"{file_path.name}: rows={len(df):,}, cols={df.shape[1]:,}")
        dfs.append(df)

    # outer merge keeps all available lab data
    merged = reduce(lambda left, right: pd.merge(left, right, on="SEQN", how="outer"), dfs)

    # tidy SEQN
    merged["SEQN"] = merged["SEQN"].astype("Int64")
    merged = merged.drop_duplicates(subset="SEQN").copy()

    # basic checks
    print("\nMerge complete")
    print("Shape:", merged.shape)
    print("Unique SEQN:", merged["SEQN"].nunique())
    print("Duplicate SEQN:", merged["SEQN"].duplicated().sum())

    print("\nTop 20 columns with highest missing values:")
    print(merged.isna().sum().sort_values(ascending=False).head(20))

    print("\nPreview:")
    print(merged.head())

    # optional: save file-level summary too
    summary_df = pd.DataFrame(file_summary)
    print("\nFile summary:")
    print(summary_df.sort_values("file").to_string(index=False))

    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved merged lab dataset to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()