import pyreadstat
import pandas as pd

file_path = "data/raw/nhanes/P_DR1TOT.xpt"

df, meta = pyreadstat.read_xport(file_path)

columns_to_keep = [
    "SEQN",
    "DR1TKCAL",  # energy
    "DR1TPROT",  # protein
    "DR1TCARB",  # carbs
    "DR1TTFAT",  # total fat
    "DR1TIRON",  # iron
    "DR1TVB12",  # vitamin B12
    "DR1TVD",  # vitamin D
    "DR1TFDFE",  # folate
    "DR1TMAGN",  # magnesium
    "DR1TZINC",  # zinc
]

diet_df = df[columns_to_keep].copy()

print(diet_df.shape)
print(diet_df.head())
print(diet_df.isna().sum())

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

print(diet_df.head())

diet_df = diet_df.drop_duplicates(subset="SEQN")

print(diet_df.shape)  # optional but useful check

diet_df.to_csv("data/processed/dietary_clean.csv", index=False)

print("Clean dietary dataset saved.")

print(diet_df["SEQN"].nunique())
