# NHANES Normalized Dataset ML Audit

- Rows: 7437
- Columns: 868
- Action counts: {"reference_normalize": 55, "untouched": 475, "zscore_normalize": 338}

## Bottom line

- Further normalization is not the main blocker now.
- The main ML risks are sentinel-coded missing values in untouched numeric survey columns, duplicate alias columns, and a long tail of very sparse or ultra-extreme continuous features.

## Likely sentinel-coded missing values

- `slq040___how_often_do_you_snort_or_stop_breathing` contains `9` in 323 rows (4.34%); flagged as likely special missing code.
- `bpq060___ever_had_blood_cholesterol_checked` contains `9` in 250 rows (3.36%); flagged as likely special missing code.
- `diq180___had_blood_tested_past_three_years` contains `9` in 174 rows (2.34%); flagged as likely special missing code.
- `mcq300a___close_relative_had_heart_attack` contains `9` in 162 rows (2.18%); flagged as likely special missing code.
- `mcq300b___close_relative_had_asthma` contains `9` in 133 rows (1.79%); flagged as likely special missing code.
- `huq051___#times_receive_healthcare_over_past_year` contains `7` in 110 rows (1.48%); flagged as likely special missing code.
- `paq655___days_vigorous_recreational_activities` contains `7` in 103 rows (1.38%); flagged as likely special missing code.
- `mcq300c___close_relative_had_diabetes` contains `9` in 90 rows (1.21%); flagged as likely special missing code.
- `mcq092___ever_receive_blood_transfusion` contains `9` in 52 rows (0.70%); flagged as likely special missing code.
- `bpq080___doctor_told_you___high_cholesterol_level` contains `9` in 37 rows (0.50%); flagged as likely special missing code.
- `smq078___how_soon_after_waking_do_you_smoke` contains `7` in 34 rows (0.46%); flagged as likely special missing code.
- `whq225___times_lost_10_lbs_or_more_to_lose_weight` contains `9` in 30 rows (0.40%); flagged as likely special missing code.
- `heq010___ever_told_you_have_hepatitis_b?` contains `9` in 29 rows (0.39%); flagged as likely special missing code.
- `heq030___ever_told_you_have_hepatitis_c?` contains `9` in 28 rows (0.38%); flagged as likely special missing code.
- `mcq170m___still_have_thyroid_problem` contains `9` in 27 rows (0.36%); flagged as likely special missing code.
- `osq230___any_metal_objects_inside_your_body?` contains `9` in 24 rows (0.32%); flagged as likely special missing code.
- `mcq035___still_have_asthma` contains `9` in 23 rows (0.31%); flagged as likely special missing code.
- `rhq078___ever_treated_for_a_pelvic_infection/pid?` contains `9` in 21 rows (0.28%); flagged as likely special missing code.
- `mcq160d___ever_told_you_had_angina` contains `9` in 20 rows (0.27%); flagged as likely special missing code.
- `diq275___past_year_dr_checked_for_a1c` contains `9` in 19 rows (0.26%); flagged as likely special missing code.

## Extreme transformed values

- `LBXHSCRP_hs_c_reactive_protein_mg_l` (reference_normalize) has 124 values with |x| > 8 and 62 with |x| > 12; max=81.287.
- `LBXSGTSI_gamma_glutamyl_transferase_ggt_iu_l` (reference_normalize) has 101 values with |x| > 8 and 58 with |x| > 12; max=112.619.
- `ggt_u_l` (reference_normalize) has 101 values with |x| > 8 and 58 with |x| > 12; max=112.619.
- `bmi` (reference_normalize) has 230 values with |x| > 8 and 32 with |x| > 12; max=22.063.
- `whq150___age_when_heaviest_weight` (zscore_normalize) has 29 values with |x| > 8 and 17 with |x| > 12; max=29.614.
- `URDACT_albumin_creatinine_ratio_mg_g` (zscore_normalize) has 26 values with |x| > 8 and 17 with |x| > 12; max=23.892.
- `uacr_mg_g` (zscore_normalize) has 26 values with |x| > 8 and 17 with |x| > 12; max=23.892.
- `LBXSCR_creatinine_refrigerated_serum_mg_dl` (reference_normalize) has 20 values with |x| > 8 and 14 with |x| > 12; max=39.467.
- `serum_creatinine_mg_dl` (reference_normalize) has 20 values with |x| > 8 and 14 with |x| > 12; max=39.467.
- `URXUMA_albumin_urine_ug_ml` (zscore_normalize) has 28 values with |x| > 8 and 13 with |x| > 12; max=22.611.
- `URXUMS_albumin_urine_mg_l` (zscore_normalize) has 28 values with |x| > 8 and 13 with |x| > 12; max=22.611.
- `LBXSASSI_aspartate_aminotransferase_ast_u_l` (reference_normalize) has 24 values with |x| > 8 and 13 with |x| > 12; max=30.933.
- `ast_u_l` (reference_normalize) has 24 values with |x| > 8 and 13 with |x| > 12; max=30.933.
- `LBDBGESI_mercury_ethyl_nmol_l` (zscore_normalize) has 20 values with |x| > 8 and 13 with |x| > 12; max=26.866.
- `LBXBGE_mercury_ethyl_ug_l` (zscore_normalize) has 20 values with |x| > 8 and 13 with |x| > 12; max=26.866.
- `liver_stiffness_kpa` (zscore_normalize) has 24 values with |x| > 8 and 12 with |x| > 12; max=16.882.
- `LBXSF3SI_5_formyl_tetrahydrofolate_nmol_l` (zscore_normalize) has 20 values with |x| > 8 and 12 with |x| > 12; max=21.340.
- `alq142___#_days_have_4_or_5_drinks/past_12_mos` (zscore_normalize) has 16 values with |x| > 8 and 12 with |x| > 12; max=16.215.
- `pad680___minutes_sedentary_activity` (zscore_normalize) has 40 values with |x| > 8 and 9 with |x| > 12; max=25.874.
- `alq170___past_30_days_#_times_4_5_drinks_on_an_oc` (zscore_normalize) has 33 values with |x| > 8 and 9 with |x| > 12; max=16.881.

## Exact duplicate columns

- `LBD4CELC_blood_1_1_1_2_tetrachloroethane_cmt_code` is exactly duplicated by `LBDV3BLC_blood_1_3_dichlorobenzene_comment_code`.
- `LBD4CELC_blood_1_1_1_2_tetrachloroethane_cmt_code` is exactly duplicated by `LBDVDELC_blood_1_2_dibromoethane_comment_code`.
- `LBD4CELC_blood_1_1_1_2_tetrachloroethane_cmt_code` is exactly duplicated by `LBDVFTLC_blood_aaa_trifluorotoluene_comment_code`.
- `LBDBSELC_blood_selenium_comment_code` is exactly duplicated by `LBDBMNLC_blood_manganese_comment_code`.
- `LBDSF1LC_5_methyl_tetrahydrofolate_cmt` is exactly duplicated by `LBDSF6LC_mefox_oxidation_product_cmt`.
- `LBX4CE_blood_1_1_1_2_tetrachloroethane_ng_ml` is exactly duplicated by `LBXVTFT_blood_aaa_trifluorotoluene_ng_ml`.
- `URDDHBLC_n_ace_s_3_4_dihidxybutl_l_cys_comt` is exactly duplicated by `URDPMMLC_n_a_s_3_hydrxprpl_1_metl_l_cys_comt`.
- `URDUCSLC_urinary_cesium_comment_code` is exactly duplicated by `URDUMOLC_urinary_molybdenum_comment_code`.
- `URXUMA_albumin_urine_ug_ml` is exactly duplicated by `URXUMS_albumin_urine_mg_l`.
- `WTFOLPRP_folate_folate_form_weight_pre_pandemic` is exactly duplicated by `WTFOLPRP__p_folfms`.
- `WTSAFPRP_fasting_subsample_weight` is exactly duplicated by `WTSAFPRP__p_ins`.
- `WTSAFPRP_fasting_subsample_weight` is exactly duplicated by `WTSAFPRP__p_trigly`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_pernt`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_uas`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_ucm`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_uhg`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_uio`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_um`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_uni`.
- `WTSAPRP_subsample_a_weights_pre_pandemic` is exactly duplicated by `WTSAPRP__p_utas`.

## Very sparse columns

- `LBXIGGA_cytomegalovirus_cmv_igg_avidity` is 100.00% missing.
- `LBXIGG_cytomegalovirus_cmv_igg` is 100.00% missing.
- `LBXIGM_cytomegalovirus_cmv_igm` is 100.00% missing.
- `mcq149___menstrual_periods_started_yet?` is 100.00% missing.
- `mcq151___age_in_years_at_first_menstrual_period` is 100.00% missing.
- `smd630___age_first_smoked_whole_cigarette` is 100.00% missing.
- `smq621___cigarettes_smoked_in_entire_life` is 100.00% missing.
- `medication_21` is 99.97% missing.
- `medication_22` is 99.97% missing.
- `medication_20` is 99.96% missing.
- `mcq230c___what_kind_of_cancer_third_mention` is 99.93% missing.
- `medication_19` is 99.93% missing.
- `mcq510b___liver_condition_non_alcoholic_fatty_liver` is 99.92% missing.
- `medication_18` is 99.91% missing.
- `cdq009g___pain_in_left_arm` is 99.85% missing.
- `cdq009c___pain_in_neck` is 99.84% missing.
- `medication_17` is 99.84% missing.
- `mcq510e___liver_condition_autoimmune` is 99.83% missing.
- `cdq009a___pain_in_right_arm` is 99.81% missing.
- `medication_16` is 99.76% missing.

## Recommendation for ML

- Keep the current normalization pipeline.
- Before training, convert flagged questionnaire sentinel codes like `7/9/77/99/7777/9999` to missing using NHANES codebooks or a curated per-column map.
- Drop one column from each exact duplicate pair to reduce redundancy and leakage-like feature duplication.
- Consider excluding columns with >95% missingness unless they are explicitly needed.
- Consider winsorizing, log-transforming, or excluding some of the most extreme long-tail continuous variables for linear models.
