# Sleep Disorder FP Audit - 2026-03-31

## Scope

Focused false-positive audit for the rebuilt `sleep_disorder` model (`sleep_disorder_lr_v3_hard_neg`) on the 760-profile NHANES cohort.

Compared runs:

- baseline: [layer1_20260330_230517.md](/Users/Philipp/AIBootcamp/halfFull/evals/reports/layer1_20260330_230517.md)
- rebuild: [layer1_20260331_090114.md](/Users/Philipp/AIBootcamp/halfFull/evals/reports/layer1_20260331_090114.md)

Definition of "new sleep FP" in this audit:

- profile is **not** a true `sleep_disorder` case
- `sleep_disorder v3 >= 0.70`
- `sleep_disorder v2 < 0.75`

This isolates the **additional** false positives introduced by the new model rather than all sleep false positives overall.

## Headline

The extra sleep false positives are mostly **older overlap profiles**, not simple healthy noise.

What stands out:

- 124 additional false positives were introduced by `v3`
- only `3/124` are healthy
- most are true disease cases from adjacent fatigue / overlap conditions
- the dominant competing explanation is `thyroid`

## Cluster Summary

### By true target condition

| Target condition | Count |
|---|---:|
| `kidney_disease` | 26 |
| `hypothyroidism` | 24 |
| `anemia` | 14 |
| `perimenopause` | 12 |
| `inflammation` | 11 |
| `liver` | 11 |
| `prediabetes` | 11 |
| `hepatitis` | 5 |
| `electrolyte_imbalance` | 3 |
| `vitamin_d_deficiency` | 3 |

### By profile type

| Profile type | Count |
|---|---:|
| `positive` | 64 |
| `multi` | 57 |
| `healthy` | 3 |

### Strongest competing condition in the same profile

| Top competing model | Count |
|---|---:|
| `thyroid` | 76 |
| `anemia` | 21 |
| `electrolyte_imbalance` | 11 |
| `perimenopause` | 7 |
| `hidden_inflammation` | 5 |

## Signal Pattern In The New FPs

Across the 124 additional sleep false positives:

- age >= 60: `84`
- BMI >= 30: `57`
- snore >= 1: `59`
- fatigue >= 1: `64`
- shortness of breath signal present: `64`
- poor general health >= 4: `58`
- nocturia >= 2: `28`
- weekday sleep <= 6 hours: only `23`

Interpretation:

- the model is **not** mainly over-firing on classic insomnia-like short-sleep profiles
- it is over-firing on an **older, heavier, tired, somewhat breathless overlap phenotype**
- that phenotype often overlaps clinically with thyroid, anemia, kidney, and peri-like cases

## Practical Takeaway

The new sleep model did improve sleep recall, but its remaining false positives are concentrated in this pattern:

1. older age
2. obesity or elevated body-size signal
3. some snoring signal
4. fatigue or poor health
5. frequent coexistence with thyroid-like or anemia-like model evidence

So the next cleanup should probably **not** be "more hard negatives for generic healthy fatigue."

The higher-value next move is:

1. add an overlap suppression rule or feature against `thyroid`-dominant profiles
2. strengthen truly sleep-specific anchors beyond broad tired / poor-health / BMI signal
3. consider a gate that requires a stronger sleep-pattern bundle when sleep is competing mostly with thyroid / anemia on older users

## Example Profiles

Representative examples from the new FP set:

- `NHANES-C-23517`: true `hypothyroidism`, `sleep_v2=0.2231`, `sleep_v3=0.7141`, top competing model `thyroid=0.7085`
- `NHANES-C-25601`: true `anemia`, `sleep_v2=0.6740`, `sleep_v3=0.9554`, top competing model `thyroid=0.7638`
- `NHANES-C-29464`: true `perimenopause`, `sleep_v2=0.4071`, `sleep_v3=0.8325`, top competing model `thyroid=0.9231`
- `NHANES-D-39584`: true `kidney_disease`, `sleep_v2=0.3053`, `sleep_v3=0.8311`, top competing models `anemia=0.8808`, `thyroid=0.8727`

These examples are consistent with a **shared overlap phenotype**, not a single-label bug.
