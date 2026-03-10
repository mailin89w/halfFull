import pandas as pd

# load Anna's questionnaire dataset
df = pd.read_csv("data/processed/merged_questionnaire.csv")

# rename the column to match the other datasets
df = df.rename(columns={"seqn___respondent_sequence_number": "SEQN"})

# convert SEQN to integer (remove .0)
df["SEQN"] = df["SEQN"].astype("Int64")

# save the corrected dataset
df.to_csv("data/processed/merged_questionnaire.csv", index=False)

print("SEQN column standardized.")

# ---- Fix Nils' examination dataset ----
examination = pd.read_csv("data/processed/examination_clean.csv")

# convert SEQN to integer
examination["SEQN"] = examination["SEQN"].astype("Int64")

# save
examination.to_csv("data/processed/examination_clean.csv", index=False)

print("Examination SEQN standardized.")
