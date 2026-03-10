from pathlib import Path
import pyreadstat
import pandas as pd


RAW_FILE = Path("data/raw/nhanes/P_DR1TOT.xpt")
OUTPUT_FILE = Path("data/processed/dietary_clean.csv")


def main() -> None:
    # Make sure the processed folder exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load NHANES dietary total nutrient intake file
    df, meta = pyreadstat.read_xport(RAW_FILE)

    # Keep only variables relevant for fatigue-related nutrition analysis
    columns_to_keep = [
        "SEQN",
        "DR1TKCAL",  # energy
        "DR1TPROT",  # protein
        "DR1TCARB",  # carbohydrates
        "DR1TTFAT",  # total fat
        "DR1TIRON",  # iron
        "DR1TVB12",  # vitamin B12
        "DR1TVD",  # vitamin D
        "DR1TFDFE",  # folate
        "DR1TMAGN",  # magnesium
        "DR1TZINC",  # zinc
    ]

    diet_df = df[columns_to_keep].copy()

    # Rename columns to readable names
    diet_df = diet_df.rename(
        columns={
            "DR1TKCAL": "calories",
            "DR1TPROT": "protein",
            "DR1TCARB": "carbs",
            "DR1TTFAT": "fat",
            "DR1TIRON": "iron",
            "DR1TVB12": "vitamin_b12",
            "DR1TVD": "vitamin_d",
            "DR1TFDFE": "folate",
            "DR1TMAGN": "magnesium",
            "DR1TZINC": "zinc",
        }
    )

    # Keep one row per participant
    diet_df = diet_df.drop_duplicates(subset="SEQN")

    # Optional quick quality checks
    print("Shape:", diet_df.shape)
    print("Unique participants:", diet_df["SEQN"].nunique())
    print("\nMissing values:")
    print(diet_df.isna().sum())
    print("\nPreview:")
    print(diet_df.head())

    # Save cleaned file
    diet_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nClean dietary dataset saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
