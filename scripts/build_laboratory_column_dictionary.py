from pathlib import Path
import pandas as pd
import pyreadstat
import re

LAB_DATA_PATH = Path("data/processed/laboratory_all_clean.csv")
LAB_RAW_DIR = Path("data/raw/nhanes/lab")
OUTPUT_PATH = Path("data/processed/laboratory_column_dictionary.csv")

lab_df = pd.read_csv(LAB_DATA_PATH)

lab_columns = pd.DataFrame({
    "original_column": lab_df.columns
})

print("Anzahl Spalten in laboratory_all_clean.csv:", len(lab_columns))
print(lab_columns.head())

def make_slug(text):
    if pd.isna(text):
        return pd.NA
    text = str(text).strip().lower()
    text = re.sub(r"[%/(),.-]+", " ", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text

metadata_rows = []

for file_path in sorted(LAB_RAW_DIR.glob("*.xpt")):
    try:
        _, meta = pyreadstat.read_xport(file_path, metadataonly=True)
    except Exception as e:
        print(f"Fehler bei {file_path.name}: {e}")
        continue

    col_names = meta.column_names
    col_labels = meta.column_labels

    for col_name, col_label in zip(col_names, col_labels):
        metadata_rows.append({
            "source_file": file_path.name,
            "original_column": col_name,
            "label": col_label
        })

lab_metadata = pd.DataFrame(metadata_rows)

print("Anzahl Metadaten-Zeilen:", len(lab_metadata))
print(lab_metadata.head(20))

duplicate_metadata = (
    lab_metadata.groupby("original_column")
    .agg(
        n_files=("source_file", "nunique"),
        files=("source_file", lambda x: " | ".join(sorted(set(x)))),
        labels=("label", lambda x: " | ".join(sorted(set(str(v) for v in x if pd.notna(v)))))
    )
    .reset_index()
)

duplicates_only = duplicate_metadata[duplicate_metadata["n_files"] > 1]

print("Doppelte original_column in Metadaten:", len(duplicates_only))
print(duplicates_only.head(20))

lab_metadata_unique = (
    lab_metadata.groupby("original_column")
    .agg(
        source_file=("source_file", lambda x: " | ".join(sorted(set(x)))),
        label=("label", lambda x: " | ".join(sorted(set(str(v) for v in x if pd.notna(v)))))
    )
    .reset_index()
)

print(lab_metadata_unique.head(20))

lab_dict = lab_columns.merge(
    lab_metadata_unique,
    on="original_column",
    how="left"
)

print("Shape lab_dict:", lab_dict.shape)
print(lab_dict.head(30))

lab_dict["readable_name_suggested"] = lab_dict["label"].apply(make_slug)

print(
    lab_dict[["original_column", "label", "readable_name_suggested"]].head(30)
)

lab_dict["readable_name_final"] = pd.NA
lab_dict["keep_status"] = "review"
lab_dict["notes"] = ""

# SEQN direkt markieren
lab_dict.loc[lab_dict["original_column"] == "SEQN", "readable_name_final"] = "SEQN"
lab_dict.loc[lab_dict["original_column"] == "SEQN", "keep_status"] = "keep_id"

print(lab_dict.head(20))

missing_labels = lab_dict[lab_dict["label"].isna()].copy()

print("Spalten ohne Label:", len(missing_labels))
print(missing_labels.head(30))

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
lab_dict.to_csv(OUTPUT_PATH, index=False)

print(f"Gespeichert unter: {OUTPUT_PATH}")