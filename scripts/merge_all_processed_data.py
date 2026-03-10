from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/processed")
OUTPUT_FILE = DATA_DIR / "nhanes_merged_adults.csv"

FILES = {
    "demo": "demo_all_adults.csv",
    "dietary": "dietary_clean.csv",
    "examination": "examination_clean.csv",
    "laboratory": "laboratory_clean.csv",
    "questionnaire": "merged_questionnaire.csv",
}


def load_csv(filename: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / filename, low_memory=False)

    if "SEQN" not in df.columns:
        raise ValueError(f"{filename} does not contain SEQN")

    df["SEQN"] = pd.to_numeric(df["SEQN"], errors="coerce").astype("Int64")
    return df


def main() -> None:
    demo = load_csv(FILES["demo"])
    dietary = load_csv(FILES["dietary"])
    examination = load_csv(FILES["examination"])
    laboratory = load_csv(FILES["laboratory"])
    questionnaire = load_csv(FILES["questionnaire"])

    merged = demo.copy()

    for name, df in [
        ("dietary", dietary),
        ("examination", examination),
        ("laboratory", laboratory),
        ("questionnaire", questionnaire),
    ]:
        before = merged.shape[0]

        merged = merged.merge(
            df,
            on="SEQN",
            how="left",
            validate="one_to_one",
        )

        after = merged.shape[0]
        print(f"Merged {name}: {before} -> {after} rows")

    merged = merged.sort_values("SEQN").reset_index(drop=True)

    print("\nFinal shape:", merged.shape)
    print("Unique SEQN:", merged["SEQN"].nunique())
    print("\nTop 20 columns by missingness:")
    print(merged.isna().sum().sort_values(ascending=False).head(20))

    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved merged dataset to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()