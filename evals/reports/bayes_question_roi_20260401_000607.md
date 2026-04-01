# Bayes Question ROI — bayes_question_roi_20260401_000607

- Cohort: `/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_800.json`
- Questions scored: `32`
- Low-gain threshold: `0.010` bits

## Summary

- Remove candidates: `3`
- Replace / refresh-data candidates: `0`
- Review low-gain: `1`
- Keep: `26`

## Current Keep / Review / Remove

| Question | Condition | Status | N valid | N invalid | Avg gain (bits) | Avg posterior delta | Top-3 gains | Top-3 losses |
|---|---|---|---:|---:|---:|---:|---:|---:|
| liver_q3 | liver | remove_candidate | 2 | 0 | -0.0699 | -0.2046 | 0 | 1 |
| liver_q2 | liver | remove_candidate | 2 | 0 | -0.0400 | -0.0568 | 0 | 1 |
| sleep_q3 | sleep_disorder | remove_candidate | 205 | 0 | -0.0041 | -0.0356 | 2 | 9 |
| inflam_q4 | inflammation | no_data | 0 | 175 | 0.0000 | 0.0000 | 0 | 0 |
| anemia_q5 | anemia | no_data | 0 | 185 | 0.0000 | 0.0000 | 0 | 0 |
| sleep_q1 | sleep_disorder | review_low_gain | 205 | 0 | 0.0011 | -0.0339 | 2 | 11 |
| liver_q4 | liver | keep | 28 | 0 | 0.0107 | 0.0281 | 3 | 2 |
| liver_q5 | liver | keep | 35 | 0 | 0.0113 | 0.0330 | 2 | 3 |
| anemia_q4 | anemia | keep | 178 | 0 | 0.0158 | -0.0157 | 2 | 8 |
| vitd_q2 | vitamin_d_deficiency | keep | 499 | 0 | 0.0169 | -0.0025 | 10 | 71 |
| kidney_q4 | kidney | keep | 245 | 0 | 0.0209 | -0.0044 | 12 | 24 |
| thyroid_q3 | thyroid | keep | 354 | 0 | 0.0220 | -0.0128 | 22 | 26 |
| vitd_q1 | vitamin_d_deficiency | keep | 499 | 0 | 0.0270 | -0.0059 | 13 | 68 |
| thyroid_q2 | thyroid | keep | 354 | 0 | 0.0275 | -0.0167 | 26 | 29 |
| inflam_q1 | inflammation | keep | 175 | 0 | 0.0289 | -0.0259 | 4 | 12 |
| elec_q2 | electrolytes | keep | 124 | 0 | 0.0313 | -0.0374 | 3 | 9 |
| iron_q3 | iron_deficiency | keep | 174 | 0 | 0.0351 | 0.0542 | 8 | 42 |
| inflam_q2 | inflammation | keep | 175 | 0 | 0.0359 | 0.0033 | 11 | 24 |
| elec_q3 | electrolytes | keep | 124 | 0 | 0.0427 | 0.0065 | 2 | 6 |
| prediabetes_q1 | prediabetes | keep | 182 | 0 | 0.0442 | 0.0806 | 41 | 1 |
| hep_q4 | hepatitis | keep | 61 | 0 | 0.0461 | -0.0200 | 2 | 9 |
| thyroid_q1 | thyroid | keep | 354 | 0 | 0.0475 | 0.0253 | 26 | 14 |
| inflam_q3 | inflammation | keep | 175 | 0 | 0.0491 | 0.0284 | 23 | 25 |
| kidney_q2 | kidney | keep | 245 | 0 | 0.0531 | 0.0069 | 24 | 29 |
| anemia_q2 | anemia | keep | 178 | 0 | 0.0549 | -0.0085 | 8 | 17 |
| elec_q4 | electrolytes | keep | 124 | 0 | 0.0580 | 0.0066 | 8 | 6 |
| iron_q5 | iron_deficiency | keep | 194 | 0 | 0.0585 | 0.0727 | 10 | 59 |
| kidney_q1 | kidney | keep | 245 | 0 | 0.0594 | 0.0140 | 19 | 28 |
| iron_q2 | iron_deficiency | keep | 174 | 0 | 0.0639 | -0.0293 | 2 | 48 |
| prediabetes_q2 | prediabetes | keep | 182 | 0 | 0.0804 | 0.0197 | 37 | 6 |
| hep_q3 | hepatitis | keep | 61 | 0 | 0.0928 | -0.0222 | 6 | 14 |
| hep_q2 | hepatitis | keep | 60 | 0 | 0.1290 | 0.0495 | 7 | 12 |

## Notes

- `remove_candidate`: negative average information gain with no compensating top-3 benefit.
- `replace_or_refresh_data`: answer schema mismatch or stale cohort-answer problem is likely dominating the metric.
- `review_low_gain`: active question with near-zero average gain on the current setup.
