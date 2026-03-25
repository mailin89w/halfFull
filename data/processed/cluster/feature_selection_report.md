# Cluster Feature Selection Report

## Anchor Feature Sweep
- Features evaluated: 73
- dpq040 rank: 1 (importance: 0.0881)

### Top 50 anchor features (recommended for UMAP input):
                                          feature  mean_importance
   dpq040___feeling_tired_or_having_little_energy         0.088084
  slq050___ever_told_doctor_had_trouble_sleeping?         0.086688
  mcq160l___ever_told_you_had_any_liver_condition         0.082793
  mcq053___taking_treatment_for_anemia/past_3_mos         0.069227
                                        med_count         0.058469
 kiq022___ever_told_you_had_weak/failing_kidneys?         0.044984
                                        age_years         0.042813
huq051___#times_receive_healthcare_over_past_year         0.032879
         heq030___ever_told_you_have_hepatitis_c?         0.029141
           diq010___doctor_told_you_have_diabetes         0.026304
                                        uacr_mg_g         0.019376
                huq010___general_health_condition         0.019241
diq070___take_diabetic_pills_to_lower_blood_sugar         0.018914
      mcq366d___doctor_told_to_reduce_fat_in_diet         0.017130
  cdq010___shortness_of_breath_on_stairs/inclines         0.015100
                                              bmi         0.014640
                                        weight_kg         0.014582
   bpq020___ever_told_you_had_high_blood_pressure         0.013539
bpq080___doctor_told_you___high_cholesterol_level         0.013069
                          total_cholesterol_mg_dl         0.012990
      sld012___sleep_hours___weekdays_or_workdays         0.012752
              pad680___minutes_sedentary_activity         0.012705
                            fasting_glucose_mg_dl         0.012573
                            hdl_cholesterol_mg_dl         0.011763
            mcq160a___ever_told_you_had_arthritis         0.011304
          mcq092___ever_receive_blood_transfusion         0.011203
ocq180___hours_worked_last_week_in_total_all_jobs         0.011079
                  sld013___sleep_hours___weekends         0.010980
    mcq080___doctor_ever_said_you_were_overweight         0.010876
    LBXWBCSI_white_blood_cell_count_1000_cells_ul         0.010508
   rhq031___had_regular_periods_in_past_12_months         0.010162
                        LBXSTP_total_protein_g_dl         0.009490
                 slq030___how_often_do_you_snore?         0.008911
   mcq520___abdominal_pain_during_past_12_months?         0.008554
alq130___avg_#_alcoholic_drinks/day___past_12_mos         0.008522
            mcq300c___close_relative_had_diabetes         0.008370
                              triglycerides_mg_dl         0.007288
         kiq005___how_often_have_urinary_leakage?         0.007080
  smq020___smoked_at_least_100_cigarettes_in_life         0.007073
            rhq060___age_at_last_menstrual_period         0.006616
          LBDLDL_ldl_cholesterol_friedewald_mg_dl         0.006240
        kiq480___how_many_times_urinate_in_night?         0.005720
smd650___avg_#_cigarettes/day_during_past_30_days         0.005631
      rhq160___how_many_times_have_been_pregnant?         0.004732
     ocq670___overall_work_schedule_past_3_months         0.004353
            smq040___do_you_now_smoke_cigarettes?         0.004335
 huq071___overnight_hospital_patient_in_last_year         0.003754
 alq151___ever_have_4/5_or_more_drinks_every_day?         0.003654
         mcq195___which_type_of_arthritis_was_it?         0.003444
        whq040___like_to_weigh_more,_less_or_same         0.003340

## Enrichment Feature Sweep
- Non-anchor NHANES features with importance >= 0.002: 60

### Top enrichment features (recommended for cluster fingerprints):
                                          feature  mean_importance
                                  fatigue_ordinal         0.028484
      mcq160m___ever_told_you_had_thyroid_problem         0.026935
                           fatigue_binary_lenient         0.019298
                            fatigue_binary_strict         0.016130
rxdcount___number_of_prescription_medicines_taken         0.015836
 rxduse___taken_prescription_medicine,_past_month         0.013309
          diq160___ever_told_you_have_prediabetes         0.012653
  mcd180l___age_when_told_you_had_liver_condition         0.011727
  mcd180m___age_when_told_you_had_thyroid_problem         0.011530
                                      prediabetes         0.011165
slq040___how_often_do_you_snort_or_stop_breathing         0.010641
             mcq170l___still_have_liver_condition         0.008053
                            LBXGH_glycohemoglobin         0.007374
                           LBXHGB_hemoglobin_g_dl         0.006727
                                LBXHCT_hematocrit         0.006439
                           serum_creatinine_mg_dl         0.006148
                           LBXHCR_hepatitis_c_rna         0.005601
                whq150___age_when_heaviest_weight         0.005335
       LBDSGLSI_glucose_refrigerated_serum_mmol_l         0.005317
          rxddays___number_of_days_taken_medicine         0.004997
       mcq366b___doctor_told_to_increase_exercise         0.004913
    LBDSCRSI_creatinine_refrigerated_serum_umol_l         0.004806
       LBXSCR_creatinine_refrigerated_serum_mg_dl         0.004748
          LBXSGL_glucose_refrigerated_serum_mg_dl         0.004720
         heq010___ever_told_you_have_hepatitis_b?         0.004371
             URDACT_albumin_creatinine_ratio_mg_g         0.004175
   LBXRBCSI_red_blood_cell_count_million_cells_ul         0.004174
bpq090d___told_to_take_prescriptn_for_cholesterol         0.004164
                              liver_stiffness_kpa         0.004098
                                        height_cm         0.003888

## Recommended Next Step
1. Review the top-50 anchor list — manually protect dpq040 and any clinically critical features
   before cutting to your final ~45 for UMAP.
2. Review the enrichment list — exclude anything that is a near-duplicate of an anchor feature
   or that would be unavailable in the NHANES enrichment step.
3. Proceed to cluster_train.py with the finalized anchor set.