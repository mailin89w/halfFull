import pandas as pd
from pathlib import Path

# Pfade
input_path = Path("data/processed/nhanes_merged_adults_final.csv")
output_path = Path("data/processed/nhanes_merged_adults_final.csv")

# Datensatz laden
df = pd.read_csv(input_path)

# Erwartete Quellspalten
col_diq010 = "diq010___doctor_told_you_have_diabetes"
col_diq160 = "diq160___ever_told_you_have_prediabetes"

# Prüfen, ob die benötigten Spalten existieren
missing_cols = [col for col in [col_diq010, col_diq160] if col not in df.columns]
if missing_cols:
    raise ValueError(f"Diese Spalten fehlen im Datensatz: {missing_cols}")

# Alte kombinierte Zielspalten entfernen, falls vorhanden
for col in ["diabetes", "prediabetes"]:
    if col in df.columns:
        df.drop(columns=col, inplace=True)

# Neue Spalte: diabetes
# 1 = Yes bei DIQ010 == 1
# 0 = No / Borderline / Don't know / missing / sonstige Werte
df["diabetes"] = (df[col_diq010] == 1).astype("Int64")

# Neue Spalte: prediabetes
# 1 = Yes bei DIQ160 == 1
# 0 = No / Don't know / missing / sonstige Werte
df["prediabetes"] = (df[col_diq160] == 1).astype("Int64")

# Speichern
df.to_csv(output_path, index=False)

print(f"Recoding abgeschlossen. Neue Datei gespeichert unter: {output_path}")
print(df[["diabetes", "prediabetes"]].value_counts(dropna=False))