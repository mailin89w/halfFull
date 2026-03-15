import json
from pathlib import Path

import joblib
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
)
from sklearn.model_selection import train_test_split


DATA_PATH = Path("data/processed/nhanes_merged_adults_final.csv")
TARGET = "anemia"
FINAL_THRESHOLD = 0.10
RANDOM_STATE = 42


FEATURES = [
    "huq071___overnight_hospital_patient_in_last_year",
    "serum_albumin_g_dl",
    "LBXSAL_albumin_refrigerated_serum_g_dl",
    "LBDSALSI_albumin_refrigerated_serum_g_l",
    "height_cm",
    "iron_deficiency",
    "LBXBMN_blood_manganese_ug_l",
    "LBDBMNSI_blood_manganese_nmol_l",
    "LBDIRNSI_iron_frozen_serum_umol_l",
    "serum_iron_ug_dl",
    "LBXIRN_iron_frozen_serum_ug_dl",
    "LBXSIR_iron_refrigerated_serum_ug_dl",
    "LBDSIRSI_iron_refrigerated_serum_umol_l",
    "huq010___general_health_condition",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "LBDSGBSI_globulin_g_l",
    "LBXSGB_globulin_g_dl",
    "cdq001___sp_ever_had_pain_or_discomfort_in_chest",
    "LBXPLTSI_platelet_count_1000_cells_ul",
    "mcq520___abdominal_pain_during_past_12_months?",
    "fatigue_ordinal",
    "mcq092___ever_receive_blood_transfusion",
    "LBXBSE_blood_selenium_ug_l",
    "LBDBSESI_blood_selenium_umol_l",
    "LBXHSCRP_hs_c_reactive_protein_mg_l",
    "dpq040___feeling_tired_or_having_little_energy",
    "kiq005___how_often_have_urinary_leakage?",
    "ocd150___type_of_work_done_last_week",
    "LBDTIBSI_tot_iron_binding_capacity_tibc_umol_l",
    "LBDTIB_total_iron_binding_capacity_tibc_ug_dl",
    "tibc_ug_dl",
    "WTFOLPRP__p_folfms",
    "WTFOLPRP_folate_folate_form_weight_pre_pandemic",
    "rxduse___taken_prescription_medicine,_past_month",
]


def load_data():
    df = pd.read_csv(DATA_PATH, low_memory=False)
    return df


def prepare_data(df):
    X = df[FEATURES]
    y = df[TARGET]
    return X, y


def split_data(X, y):
    return train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )


def impute_data(X_train, X_test):
    imputer = SimpleImputer(strategy="median")

    X_train = pd.DataFrame(
        imputer.fit_transform(X_train),
        columns=X_train.columns,
        index=X_train.index,
    )

    X_test = pd.DataFrame(
        imputer.transform(X_test),
        columns=X_test.columns,
        index=X_test.index,
    )

    return X_train, X_test, imputer


def apply_smote(X_train, y_train):
    smote = SMOTE(random_state=RANDOM_STATE)
    X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)

    X_train_smote = pd.DataFrame(X_train_smote, columns=X_train.columns)
    y_train_smote = pd.Series(y_train_smote)

    return X_train_smote, y_train_smote


def train_model(X_train, y_train):
    model = GradientBoostingClassifier(random_state=RANDOM_STATE)
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test):
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= FINAL_THRESHOLD).astype(int)

    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("Precision:", precision_score(y_test, y_pred))
    print("Recall:", recall_score(y_test, y_pred))
    print("F1:", f1_score(y_test, y_pred))
    print("ROC AUC:", roc_auc_score(y_test, y_proba))
    print()
    print(classification_report(y_test, y_pred))


def save_model(model, imputer):
    output_dir = Path("artifacts/anemia_model")
    output_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, output_dir / "anemia_model.joblib")
    joblib.dump(imputer, output_dir / "anemia_imputer.joblib")

    with open(output_dir / "features.json", "w") as f:
        json.dump(FEATURES, f)

    with open(output_dir / "threshold.json", "w") as f:
        json.dump({"threshold": FINAL_THRESHOLD}, f)


def main():

    print("Loading data...")
    df = load_data()

    print("Preparing features...")
    X, y = prepare_data(df)

    print("Splitting dataset...")
    X_train, X_test, y_train, y_test = split_data(X, y)

    print("Imputing missing values...")
    X_train, X_test, imputer = impute_data(X_train, X_test)

    print("Applying SMOTE...")
    X_train_smote, y_train_smote = apply_smote(X_train, y_train)

    print("Training Gradient Boosting model...")
    model = train_model(X_train_smote, y_train_smote)

    print("Evaluating model...")
    evaluate_model(model, X_test, y_test)

    print("Saving model artifacts...")
    save_model(model, imputer)

    print("Done.")


if __name__ == "__main__":
    main()
