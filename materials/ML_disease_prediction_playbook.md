# ML Disease Prediction Playbook
### NHANES Binary Classification — Full Workflow

> **Purpose**: Step-by-step template for building, evaluating, and saving an interpretable
> screening model for any binary disease target in the NHANES dataset.
> All design decisions are documented, including what was tried, what failed, and why.

---

## 0. Context & Constraints

| Property | Value |
|---|---|
| Dataset | `data/processed/nhanes_merged_adults_final.csv` |
| Population | Adults only |
| Imbalance | Typically 5–15% positive (use `class_weight='balanced'` throughout) |
| Goal | **Screening** — optimise for **recall over precision** |
| No-go | Neural nets (excluded from this workflow) |
| Environment | `ml_project_env` — Python 3.11, sklearn 1.8, notebook `notebooks/ML_<disease>.ipynb` |
| Seed | `SEED = 42` everywhere |

---

## 1. Notebook Setup

**Notebook name**: `notebooks/ML_<disease>.ipynb`

### 1.1 Column mapping

The raw CSV uses long mangled column names (e.g. `LBXHGB_hemoglobin_g_dl`).
Build a `FEATURE_MAP` dict: `{friendly_name: raw_column_name}`.

Key rules:
- Include `thyroid` (or target disease) as the last entry
- For blood pressure / pulse: average the 3 repeated readings into `sbp_mean`, `dbp_mean`, `pulse_mean`
- Encode all `object`/`category` columns with `pd.Categorical().codes` (−1 → NaN)
- Drop rows where the target is null; cast target to `int`

```python
_valid = {k: v for k, v in FEATURE_MAP.items() if v in df_raw.columns}
df = df_raw[list(_valid.values())].copy()
df.columns = list(_valid.keys())
for pfx in ['sbp', 'dbp', 'pulse']:
    cs = [c for c in df.columns if c.startswith(f'{pfx}_')]
    if cs:
        df[f'{pfx}_mean'] = df[cs].mean(axis=1)
        df.drop(columns=cs, inplace=True)
TARGET = '<disease>'
df = df.dropna(subset=[TARGET])
df[TARGET] = df[TARGET].astype(int)
for col in df.select_dtypes(include=['object', 'category']).columns:
    if col != TARGET:
        df[col] = pd.Categorical(df[col]).codes.astype(float).replace(-1, np.nan)
```

---

## 2. Exploratory Data Analysis (EDA)

Run all EDA **before** any modelling.

### 2.1 Class balance
```python
print(df[TARGET].value_counts())
print(f"Positive rate: {df[TARGET].mean()*100:.1f}%")
```
→ Report imbalance ratio. If >10:1, confirm `class_weight='balanced'` is used everywhere.

### 2.2 Missing data
```python
miss = df.isnull().mean().sort_values(ascending=False)
miss[miss > 0].plot.bar()
```
→ Note columns with >50% missing. **Do NOT drop them** — add missingness flags instead (see §4).

### 2.3 Feature distributions by target
- Histograms / KDE for continuous features, split by target=0 vs target=1
- Mann-Whitney U test for each feature; report top 20 by p-value
- Box plots for the most significant features

### 2.4 Correlation heatmap
```python
sns.heatmap(df[features].corr(), cmap='coolwarm', center=0)
```
→ Flag highly correlated pairs (|r| > 0.8); they may cause instability in unpenalised models.

---

## 3. Feature Groups

Split features into two domains before modelling (used in ensemble §7):

**LAB_FEATURES** (~40): CBC, lipids, metabolic panel, liver, renal, electrolytes,
iron studies, inflammation markers (CRP), vitals (SBP/DBP/pulse).

**QUEST_FEATURES** (~51): Demographics (age, gender, BMI, waist, weight),
sleep, activity, smoking, alcohol, nutrition, self-reported conditions, medications.

```python
LAB_FEATURES  = [c for c in [...] if c in df.columns]
QUEST_FEATURES = [c for c in [...] if c in df.columns]
ALL_FEATURES  = list(dict.fromkeys(LAB_FEATURES + QUEST_FEATURES))
```

---

## 4. Preprocessing — Missingness Flags (Critical)

**Do not drop high-missing columns.** Instead, add a binary `_miss` flag for every
column that has any NaN. The model learns from *whether a test was done* as well as the value.

```python
def add_missing_flags(df_feat):
    flags = {f'{c}_miss': df_feat[c].isnull().astype(int)
             for c in df_feat.columns if df_feat[c].isnull().any()}
    return pd.concat([df_feat, pd.DataFrame(flags, index=df_feat.index)], axis=1) \
           if flags else df_feat

X_lab_full   = add_missing_flags(df[LAB_FEATURES])
X_quest_full = add_missing_flags(df[QUEST_FEATURES])
X_all_full   = add_missing_flags(df[ALL_FEATURES])
y_full       = df[TARGET]
```

### Train/test split — always use integer indices

```python
_idx = np.arange(len(df))
tr_idx, te_idx = train_test_split(_idx, test_size=0.2,
                                   stratify=y_full.values, random_state=SEED)
X_tr = X_all_full.iloc[tr_idx];  X_te = X_all_full.iloc[te_idx]
y_tr = y_full.iloc[tr_idx];       y_te = y_full.iloc[te_idx]
```

> **Why integer indices?** Avoids index misalignment when slicing DataFrames built
> from different feature subsets.

### Standard pipeline template

```python
def make_lr(C=1.0, penalty='l2'):
    return Pipeline([
        ('imp', SimpleImputer(strategy='median')),
        ('sc',  StandardScaler()),
        ('clf', LogisticRegression(penalty=penalty, C=C,
                                   class_weight='balanced',
                                   max_iter=2000, random_state=SEED,
                                   solver='lbfgs'))  # liblinear for L1
    ])

def make_rf():
    return Pipeline([
        ('imp', SimpleImputer(strategy='median')),
        ('sc',  StandardScaler()),
        ('clf', RandomForestClassifier(n_estimators=200,
                                        class_weight='balanced',
                                        random_state=SEED, n_jobs=-1))
    ])
```

---

## 5. Baseline Models (Section 4)

Train **LR L2** and **LR L1** on `X_all_full` (all features + miss flags).

```python
lr_l2 = make_lr(C=1.0, penalty='l2')
lr_l2.fit(X_tr, y_tr)

lr_l1 = make_lr(C=1.0, penalty='l1')   # solver='liblinear'
lr_l1.fit(X_tr, y_tr)
```

**Evaluation at `thr=0.3`** (standard screening threshold):

```python
THR = 0.3
prob = model.predict_proba(X_te)[:, 1]
pred = (prob >= THR).astype(int)

metrics = {
    'ROC-AUC':        roc_auc_score(y_te, prob),
    'Avg Precision':  average_precision_score(y_te, prob),
    'Recall':         recall_score(y_te, pred),
    'Precision':      precision_score(y_te, pred, zero_division=0),
    'Accuracy':       accuracy_score(y_te, pred),
    'F1':             f1_score(y_te, pred, zero_division=0),
}
```

**Always produce:**
- ROC curve
- Precision-Recall curve
- Confusion matrix at thr=0.3
- Calibration curve
- Threshold sweep (thr 0.01–0.90): plot recall, precision, F1 vs threshold
- 5-fold CV box plots

**Find optimal threshold for recall ≥ 0.85:**
```python
thrs = np.arange(0.01, 0.91, 0.01)
thr_df = pd.DataFrame([
    {'thr': t,
     'recall':    recall_score(y_te, (prob>=t).astype(int), zero_division=0),
     'precision': precision_score(y_te, (prob>=t).astype(int), zero_division=0)}
    for t in thrs
])
opt = thr_df[thr_df['recall'] >= 0.85].iloc[-1]
```

---

## 6. Tree Models: Random Forest + XGBoost (Section 7–8)

```python
from xgboost import XGBClassifier

# Imbalance ratio for XGBoost
spw = (y_tr == 0).sum() / (y_tr == 1).sum()

rf = make_rf()
rf.fit(X_tr, y_tr)

xgb_pipe = Pipeline([
    ('imp', SimpleImputer(strategy='median')),
    ('clf', XGBClassifier(n_estimators=200, scale_pos_weight=spw,
                          random_state=SEED, eval_metric='logloss',
                          use_label_encoder=False))
])
xgb_pipe.fit(X_tr, y_tr)
```

**Produce comparison plots**: ROC, PR, confusion matrices, feature importances,
threshold sweep side-by-side with LR.

**Expected finding**: LR typically matches or beats tree models on recall at thr=0.3
for NHANES disease targets. Tree models need a much lower threshold (e.g. 0.03)
to reach the same recall.

---

## 7. Calibration (Section 10)

Calibrate RF and XGBoost only (LR is already well-calibrated):

```python
from sklearn.calibration import CalibratedClassifierCV

cal_rf  = CalibratedClassifierCV(make_rf(),  method='isotonic', cv=3)
cal_xgb = CalibratedClassifierCV(xgb_pipe,   method='isotonic', cv=3)
cal_rf.fit(X_tr, y_tr)
cal_xgb.fit(X_tr, y_tr)
```

**Expected finding**: Calibration compresses probabilities toward 0.5 → recall at
thr=0.3 gets worse. Tree models need thr≈0.03 to recover recall ≥ 0.85.
All models converge to similar precision (~10–12%) at that recall level.

---

## 8. Ensemble: Domain-Split + Stacking (Section 12)

Three base models:
1. `LR_labs` trained on `X_lab_full` (lab features + miss flags)
2. `LR_quest` trained on `X_quest_full` (questionnaire features + miss flags)
3. `RF_all` trained on `X_all_full` (all features + miss flags)

**OOF stacking** (no data leakage — use `cross_val_predict`):

```python
from sklearn.model_selection import cross_val_predict as cvp

cv3 = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED)
oof_lab   = cvp(make_lr(), X_lab_full,   y_full, cv=cv3, method='predict_proba')[:,1]
oof_quest = cvp(make_lr(), X_quest_full, y_full, cv=cv3, method='predict_proba')[:,1]
oof_rf    = cvp(make_rf(), X_all_full,   y_full, cv=cv3, method='predict_proba')[:,1]

meta_X = np.column_stack([oof_lab, oof_quest, oof_rf])
meta_lr = LogisticRegression(C=1.0, class_weight='balanced', random_state=SEED)
meta_lr.fit(meta_X[tr_idx], y_tr)
```

Also try soft vote (equal weights and questionnaire-heavy weights).

**Key question to answer**: Does `LR_quest` alone match the stack?
Compare AUC and recall on the test set. If the gap is ≤0.003 AUC and ≤1 patient,
recommend shipping `LR_quest` alone (simpler, no lab dependency).

Check meta-learner weights: if labs coefficient ≈ 0, labs add no value.

---

## 9. Master Comparison Table (Section 14)

Retrain **all models consistently** on the missingness-flags dataset (X_all_full / X_lab_full / X_quest_full).
Build a single comparison DataFrame:

```python
master = pd.DataFrame([
    {'Model': name,
     'ROC-AUC': auc, 'Avg Precision': ap,
     'Recall': rec, 'Precision': prec,
     'Accuracy': acc, 'F1': f1}
    for name, auc, ap, rec, prec, acc, f1 in results
]).set_index('Model')
```

Include: LR L2, LR L1, LR Labs, LR Quest, RF, XGBoost, Cal-RF, Cal-XGBoost,
Soft-Vote (equal), Soft-Vote (LR-heavy), Stack (LR meta).

Also produce an **optimised threshold table**: for each model find the highest
threshold where recall ≥ 0.85, report that threshold + its precision.

---

## 10. Feature Selection — LR Questionnaire Model (Section 15)

Run on `LR_quest` (questionnaire features only — no lab dependency).

### 10.1 Bootstrap coefficient stability (500 resamples)

```python
N_BOOT = 500
np.random.seed(SEED)
# Pre-process once
X_proc = StandardScaler().fit_transform(
    SimpleImputer(strategy='median').fit_transform(X_quest_full[QUEST_FEATURES]))

boot_coefs = np.zeros((N_BOOT, len(QUEST_FEATURES)))
lr_boot = LogisticRegression(penalty='l2', C=1.0, class_weight='balanced',
                              max_iter=2000, solver='lbfgs', random_state=SEED)
for i in range(N_BOOT):
    idx = np.random.choice(len(X_proc), len(X_proc), replace=True)
    lr_boot.fit(X_proc[idx], y_full.values[idx])
    boot_coefs[i] = lr_boot.coef_[0]

ci_lo = np.percentile(boot_coefs, 2.5,  axis=0)
ci_hi = np.percentile(boot_coefs, 97.5, axis=0)
ci_crosses_zero = (ci_lo < 0) & (ci_hi > 0)   # True = unstable = remove
```

Plot horizontal bar chart with 95% CI error bars. Colour by stability.

### 10.2 L1 regularisation path

```python
C_vals = [0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
survival = {}
for c in C_vals:
    m = LogisticRegression(penalty='l1', C=c, class_weight='balanced',
                           max_iter=2000, solver='liblinear', random_state=SEED)
    m.fit(X_proc, y_full.values)
    survival[f'C={c}'] = (np.abs(m.coef_[0]) > 1e-6).astype(int)
surv_df = pd.DataFrame(survival, index=QUEST_FEATURES)
```

Plot as heatmap (1=nonzero, 0=zeroed out). Features zeroed at C≤0.1 are weak.

### 10.3 Feature tier classification

| Tier | Criterion | Action |
|---|---|---|
| **STRONG** | CI does not cross zero in bootstrap | Keep — core model features |
| **BORDERLINE** | CI crosses zero BUT L1 survival ≥ 3/6 | Include with caution |
| **REMOVE** | CI crosses zero AND L1 survival < 3/6 | Drop |

> **Note**: Only include features in STRONG/BORDERLINE that are actually in `QUEST_FEATURES`.
> Do **not** include lab/vitals features (sbp_mean, dbp_mean, pulse_mean) in the
> questionnaire tier lists — they belong to LAB_FEATURES even if they appear in df.columns.

### 10.4 Cross-validate three feature set sizes

```python
configs = [
    ('All quest. features',             QUEST_FEATURES),
    ('Strong only',                     STRONG),
    (f'{len(STRONG+BORDERLINE)} strong+borderline', STRONG + BORDERLINE),
]
cv5 = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
for label, feats in configs:
    s = cross_validate(make_lr(), df[[f for f in feats if f in df.columns]], y_full,
                       cv=cv5, scoring=['roc_auc','average_precision','recall'])
    # report mean ± std
```

**Expected finding**: The STRONG-only model often equals or beats the full set
(fewer features = better regularisation = better generalisation on correlated NHANES data).

---

## 11. User-Curated Feature Set (Section 17)

Present the full tier table to the user and ask them to choose a final feature list.
They may remove or add features based on domain knowledge or deployment constraints
(e.g. "exclude lab values", "remove items not in our intake form").

Re-train LR L2 on the user's chosen subset with miss flags. Produce full evaluation:
ROC, PR, confusion matrix at thr=0.3 and optimal thr, threshold sweep, coefficient plot,
5-fold CV, comparison table vs earlier models.

**Key metrics to report side-by-side with the full-feature model:**
- Test ROC-AUC
- CV ROC-AUC ± std
- Recall @ thr=0.3 (absolute and as X/N positives caught)
- False positives @ thr=0.3
- Optimal threshold for recall ≥ 0.85 + its precision

---

## 12. Single-Feature Ablation (Section 17b)

For any feature the user wants to validate, remove it and retrain.
Report the same metrics. Key things to measure:
- ΔAUC (test and CV)
- ΔRecall @ thr=0.3 (and Δ false positives)
- CV stability (does std increase?)
- Does any other feature's coefficient change dramatically? (indicates correlation/confounding)

---

## 13. Outlier / Population Filter Experiments (Section 18)

For high-leverage continuous features (e.g. `med_count`), test whether extreme values
are driving performance by training on filtered subsets:

```python
for cap, label in [(10, 'med_count ≤ 10'), (5, 'med_count ≤ 5')]:
    df_sub = df[df['med_count'] <= cap].copy()
    # retrain + evaluate identically
```

For each filter, check:
1. How many rows removed and their disease prevalence (usually 3× the baseline rate)
2. AUC, recall, CV stability vs unfiltered model
3. Whether the filtered group is the high-risk population the model needs to catch

**Expected finding**: High values of comorbidity proxies (e.g. polypharmacy)
are enriched for the disease. Removing them degrades AUC and is clinically wrong —
these patients are exactly whom you want to flag.

---

## 14. Model Export (Section 19 / `models/`)

### Files to save

```
models/
├── <disease>_lr_l2_<N>feat.joblib          # trained sklearn Pipeline
├── <disease>_lr_l2_<N>feat_metadata.json   # metrics, features, thresholds
└── predict.py                              # ThyroidPredictor-style inference class
```

### Production model: train on FULL dataset (no train/test split)

```python
pipe_prod = make_lr()
pipe_prod.fit(X_full, y_full)            # ALL rows, including test set
joblib.dump(pipe_prod, MODEL_PATH, compress=3)
```

Hold-out metrics (for reporting) come from the 80/20 eval model trained separately.

### Metadata JSON — required fields

```json
{
  "model_name":         "<disease>_lr_l2_<N>feat",
  "model_version":      "1.0.0",
  "description":        "...",
  "n_train_total":      7437,
  "n_positive":         462,
  "prevalence_pct":     6.21,
  "base_features":      [...],
  "miss_flag_features": [...],
  "all_features":       [...],
  "n_features_total":   25,
  "threshold_default":  0.3,
  "threshold_screening": 0.41,
  "holdout_eval": {
    "roc_auc": 0.8011,
    "recall_at_default_thr": 0.9239,
    "precision_at_default_thr": 0.0929,
    "recall_at_screening_thr": 0.8587,
    "precision_at_screening_thr": 0.1186,
    "confusion_matrix_default": [[566, 830], [7, 85]]
  },
  "cv_5fold": {
    "roc_auc_mean": 0.7846, "roc_auc_std": 0.0169,
    "recall_mean": 0.7207,  "recall_std": 0.0634
  },
  "coefficients":   {"feature_name": coef_value, ...},
  "intercept":      -1.234,
  "sklearn_version": "1.8.0",
  "trained_on":     "NHANES merged adults — full dataset"
}
```

### Inference class (`predict.py`) — required methods

```python
class <Disease>Predictor:
    BASE_FEATURES = [...]   # the N base features (no miss flags)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray   # scores 0-1
    def predict(self, X, threshold=None) -> np.ndarray       # binary
    def score_one(self, record: dict, threshold=None) -> dict # single patient
    def feature_importance(self) -> pd.DataFrame             # sorted coef table
    def summary(self) -> None                                # print model card
    def _prepare(self, X) -> pd.DataFrame                   # add miss flags, reorder cols
```

`_prepare` must handle partial inputs gracefully (fill missing base features with NaN).

---

## 15. Execution Tips

### Run new sections without re-executing the full notebook

Create a mini-notebook with the self-contained setup cell + new section cells,
run it, then copy outputs back to the main notebook:

```python
import json
with open('notebooks/ML_<disease>.ipynb', 'r') as f:
    nb = json.load(f)

mini = {"nbformat": nb["nbformat"], "nbformat_minor": nb["nbformat_minor"],
        "metadata": nb["metadata"],
        "cells": nb["cells"][SETUP_CELL_IDX:SETUP_CELL_IDX+3] + nb["cells"][NEW_SECTION_START:]}

for cell in mini["cells"]:
    if cell["cell_type"] == "code":
        cell["outputs"] = []
        cell["execution_count"] = None

with open('notebooks/mini_temp.ipynb', 'w') as f:
    json.dump(mini, f)
```

Then execute: `jupyter nbconvert --to notebook --execute --output ... mini_temp.ipynb`

The section 12 setup cell is designed to be **self-contained** — it re-imports everything
and rebuilds `df` from scratch, so any section from 12 onwards can run independently.

### Slow cells to watch for
- `RandomForestClassifier` with `cross_val_predict` (3+ folds × 200 trees): use `n_estimators=200`, `cv=3`
- Bootstrap (500 resamples): LR only, fast (~30s); pre-process X once outside the loop
- `CalibratedClassifierCV`: use `cv=3`, not 5

---

## 16. Decision Log — What We Tried and Why

| Decision | Reasoning |
|---|---|
| Keep >50% missing columns + miss flags | Lab missingness is itself a clinical signal (ordered tests → suspected disease). Dropping loses information. |
| `class_weight='balanced'` everywhere | 15:1 imbalance; without it, models predict all-negative trivially. |
| thr=0.3 as standard | Screening context: recall >> precision. Default 0.5 misses 60%+ of positives. |
| LR as primary model | Interpretable coefficients, competitive AUC on tabular NHANES data, fast, calibrated. Tree models offered no AUC benefit and much worse recall at thr=0.3. |
| Bootstrap for feature significance, not statsmodels | Statsmodels MLE fails (Hessian singular) with 51 correlated features + L2 penalty. Bootstrap CI is the correct approach for penalised regression. |
| Train production model on full dataset | Hold-out is for reporting metrics only. The deployed model should use all available data. |
| Integer index splits | `train_test_split` on a DataFrame with a non-default index causes misalignment when subsetting. `np.arange(len(df))` → `.iloc[idx]` is safe. |
| OOF stacking, not in-sample | Fitting meta-learner on in-sample base-model predictions leaks. `cross_val_predict` with cv=3 gives honest out-of-fold predictions. |
| `solver='lbfgs'` for L2, `'liblinear'` for L1 | lbfgs is faster and more stable for L2; liblinear is required for L1 in sklearn. |

---

## 17. Final Checklist Before Moving to Another Disease

- [ ] Notebook runs end-to-end without errors (mini-notebook approach for slow sections)
- [ ] All section cells have outputs committed to the `.ipynb`
- [ ] `models/<disease>_lr_l2_<N>feat.joblib` saved
- [ ] `models/<disease>_lr_l2_<N>feat_metadata.json` saved with all required fields
- [ ] `models/predict.py` updated or new `<disease>_predict.py` created
- [ ] `predict.py` smoke-tested standalone (`python models/predict.py`)
- [ ] Feature list documented: STRONG (with interpretation) + BORDERLINE + REMOVE
- [ ] Section 16 markdown in notebook: final feature table with direction (↑/↓) and clinical interpretation

---

## Appendix A — Thyroid Model Benchmark (Reference)

| Model | Features | Test AUC | CV AUC | Recall@0.3 | Prec@0.3 |
|---|---|---|---|---|---|
| LR L2 (all 51 quest.) | 51 + flags | 0.7940 | 0.7811±0.015 | 0.913 | 0.090 |
| LR L2 (12 strong) | 12 | — | 0.7888±0.014 | — | — |
| LR L2 (18 selected) | 18 + 7 flags | **0.8011** | 0.7846±0.017 | **0.924** | 0.093 |
| LR L2 (17, no med_count) | 17 + 7 flags | 0.7783 | 0.7591±0.026 | 0.935 | 0.089 |
| RF (all feat.) | 91 + flags | 0.7940 | — | 0.315 | 0.110 |
| XGBoost (all feat.) | 91 + flags | 0.7440 | — | 0.457 | 0.091 |
| Stack (LR meta) | 3 base models | 0.7970 | — | ~0.913 | ~0.090 |

**Thyroid winner**: LR L2, 18 questionnaire features (no labs), full database, `thr=0.3`.

**Screening operating point**: `thr=0.41` → recall=85.9%, precision=11.9%
(~1 false positive per 8 referrals).

---

## Appendix B — Feature Tier Results (Thyroid)

### STRONG (9 kept in final model)
| Feature | Direction | Interpretation |
|---|---|---|
| `age_years` | ↑ | Risk rises with age |
| `gender` | ↓ | Female gender strongly associated |
| `med_count` | ↑ | More medications = higher comorbidity burden |
| `avg_drinks_per_day` | ↓ | Alcohol use lower in thyroid patients |
| `general_health_condition` | ↑ | Poor self-rated health proxies chronic illness |
| `doctor_said_overweight` | ↓ | Clinical profile differences |
| `told_dr_trouble_sleeping` | ↓ | Sleep complaints common but paradoxically negative |
| `tried_to_lose_weight` | ↓ | Weight management attempts pre-diagnosis |
| `avg_cigarettes_per_day` | ↓ | Smoking associated with lower autoimmune thyroid risk |

*(dropped from STRONG-12 but still valid: `waist_cm`, `vitamin_b12`, `income_poverty_ratio`)*

### BORDERLINE (9 kept in final model)
`weight_kg`, `pregnancy_status`, `moderate_recreational`, `times_urinate_in_night`,
`overall_work_schedule`, `ever_told_high_cholesterol`, `ever_told_diabetes`,
`taking_anemia_treatment`, `sleep_hours_weekdays`

### REMOVE (22 features — add noise, not signal)
`bmi`, `height_cm`, `education`, `sleep_hours_weekends`, `snort_or_stop_breathing`,
`feeling_tired_little_energy`, `minutes_sedentary`, `vigorous_recreational`,
`min_vigorous_recreational`, `min_moderate_recreational`, `smoked_100_cigarettes_life`,
`do_you_smoke_now`, `ever_had_alcohol`, `how_often_drink_past_12mo`, `fat`,
`vitamin_d`, `folate`, `how_consider_your_weight`, `ever_told_high_bp`,
`ever_told_asthma`, `seen_mental_health_prof`, `abdominal_pain_past_12mo`
