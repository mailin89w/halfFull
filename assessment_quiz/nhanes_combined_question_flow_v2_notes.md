# NHANES Combined Question Flow v2

This file was rebuilt around the latest feature summary and production model-runner targets.

## What changed

- Questions are grouped logically: profile, sleep/work, alcohol/smoking, cardiometabolic history, urinary/kidney, respiratory/pain, female reproductive, weight/prevention, and optional checkup values.
- Branches are defined where the frontend can skip irrelevant questions, for example non-female reproductive items, asthma-attack follow-ups only after asthma, and urinary follow-ups only after leakage.
- `_miss` features are not user-entered. They are intended to be created automatically by the transformer from whether the base field is present.
- Optional recent-checkup fields are included because several production models expect raw numeric inputs such as cholesterol, glucose, UACR, WBC, or blood pressure values in addition to questionnaire variables.

## Source set

- DEMO: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DEMO.htm
- HUQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_HUQ.htm
- DPQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DPQ.htm
- SLQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_SLQ.htm
- ALQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_ALQ.htm
- BPQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_BPQ.htm
- DIQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DIQ.htm
- KIQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_KIQ_U.htm
- MCQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_MCQ.htm
- RHQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_RHQ.htm
- SMQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_SMQ.htm
- OCQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/OCQ_J.htm
- WHQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2001/DataFiles/WHQ_B.htm
- CDQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_CDQ.htm
- HEQ: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_HEQ.htm

## Important implementation note

- Production inflammation scoring should use `models/inflammation_lr_l1_45feat.joblib`. Its metadata contains 46 input columns because one coefficient was zeroed out, but the saved production artifact is the 45-feature L1 model.
