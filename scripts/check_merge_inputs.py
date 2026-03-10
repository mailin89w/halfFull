from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/processed")

FILES = {
    "demo": "demo_all_adults.csv",
    "dietary": "dietary_clean.csv",
    "examination": "examination_clean.csv",
    "laboratory": "laboratory_clean.csv",
    "questionnaire": "merged_questionnaire.csv",
}


def load_csv(name: str, filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    df = pd.read_csv(path)

    print(f"\n=== {name.upper()} ===")
    print(f"File: {filename}")
    print(f"Shape: {df.shape}")

    if "SEQN" not in df.columns:
        raise ValueError(f"{filename} is missing SEQN")

    df["SEQN"] = pd.to_numeric(df["SEQN"], errors="coerce").astype("Int64")

    print(f"SEQN missing: {df['SEQN'].isna().sum()}")
    print(f"Unique SEQN: {df['SEQN'].nunique()}")
    print(f"Duplicate SEQN rows: {df['SEQN'].duplicated().sum()}")

    return df


def compare_overlap(base_name: str, base_df: pd.DataFrame, other_name: str, other_df: pd.DataFrame) -> None:
    base_ids = set(base_df["SEQN"].dropna())
    other_ids = set(other_df["SEQN"].dropna())

    overlap = base_ids & other_ids
    only_base = base_ids - other_ids
    only_other = other_ids - base_ids

    print(f"\n--- OVERLAP: {base_name} vs {other_name} ---")
    print(f"In both: {len(overlap)}")
    print(f"Only in {base_name}: {len(only_base)}")
    print(f"Only in {other_name}: {len(only_other)}")


def check_column_collisions(tables: dict[str, pd.DataFrame]) -> None:
    print("\n=== COLUMN COLLISIONS (excluding SEQN) ===")
    seen = {}
    collisions = {}

    for name, df in tables.items():
        for col in df.columns:
            if col == "SEQN":
                continue
            if col in seen:
                collisions.setdefault(col, []).append(name)
                if seen[col] not in collisions[col]:
                    collisions[col].insert(0, seen[col])
            else:
                seen[col] = name

    if not collisions:
        print("No duplicate column names across files.")
    else:
        for col, sources in sorted(collisions.items()):
            print(f"{col}: {sources}")


def main() -> None:
    tables = {name: load_csv(name, filename) for name, filename in FILES.items()}

    base = tables["demo"]

    for name in ["dietary", "examination", "laboratory", "questionnaire"]:
        compare_overlap("demo", base, name, tables[name])

    check_column_collisions(tables)

    print("\n=== SMALL PREVIEW OF SEQN ALIGNMENT ===")
    merged_preview = base[["SEQN"]].copy()
    for name in ["dietary", "examination", "laboratory", "questionnaire"]:
        merged_preview = merged_preview.merge(
            tables[name][["SEQN"]],
            on="SEQN",
            how="left",
            indicator=f"matched_{name}",
        )
        merged_preview[f"matched_{name}"] = merged_preview[f"matched_{name}"].map(
            {"both": 1, "left_only": 0}
        )

    print(merged_preview.head(10))


if __name__ == "__main__":
    main()