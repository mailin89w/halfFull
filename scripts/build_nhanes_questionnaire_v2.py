from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/Users/annaesakova/aipm/halfFull")
OUT_JSON = ROOT / "assessment_quiz/nhanes_combined_question_flow_v2.json"
OUT_MD = ROOT / "assessment_quiz/nhanes_combined_question_flow_v2_notes.md"


SOURCES = {
    "DEMO": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DEMO.htm",
    "HUQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_HUQ.htm",
    "DPQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DPQ.htm",
    "SLQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_SLQ.htm",
    "ALQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_ALQ.htm",
    "BPQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_BPQ.htm",
    "DIQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_DIQ.htm",
    "KIQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_KIQ_U.htm",
    "MCQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_MCQ.htm",
    "RHQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_RHQ.htm",
    "SMQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_SMQ.htm",
    "OCQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/OCQ_J.htm",
    "WHQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2001/DataFiles/WHQ_B.htm",
    "CDQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_CDQ.htm",
    "HEQ": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/P_HEQ.htm",
}


def coded(value: int | str, label: str) -> dict:
    return {"value": value, "label": label}


YES_NO = [coded(1, "Yes"), coded(2, "No"), coded(7, "Refused"), coded(9, "Don't know")]
YES_NO_BORDERLINE = [
    coded(1, "Yes"),
    coded(2, "No"),
    coded(3, "Borderline"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
GENERAL_HEALTH = [
    coded(1, "Excellent"),
    coded(2, "Very good"),
    coded(3, "Good"),
    coded(4, "Fair"),
    coded(5, "Poor"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
PHQ_FREQUENCY = [
    coded(0, "Not at all"),
    coded(1, "Several days"),
    coded(2, "More than half the days"),
    coded(3, "Nearly every day"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
SNORE_FREQUENCY = [
    coded(0, "Never"),
    coded(1, "Rarely (1-2 nights/week)"),
    coded(2, "Occasionally (3-4 nights/week)"),
    coded(3, "Frequently (5 or more nights/week)"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
GENDER = [coded(1, "Male"), coded(2, "Female")]
EDUCATION = [
    coded(1, "Less than 9th grade"),
    coded(2, "9-11th grade / includes 12th with no diploma"),
    coded(3, "High school graduate / GED or equivalent"),
    coded(4, "Some college or AA degree"),
    coded(5, "College graduate or above"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
PREGNANCY = [
    coded(1, "Pregnant"),
    coded(2, "Not pregnant"),
    coded(3, "Cannot ascertain"),
]
WEIGHT_PREFERENCE = [
    coded(1, "More"),
    coded(2, "Less"),
    coded(3, "Stay about the same"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
SMOKE_NOW = [
    coded(1, "Every day"),
    coded(2, "Some days"),
    coded(3, "Not at all"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
TIME_TO_FIRST_CIG = [
    coded(1, "Within 5 minutes"),
    coded(2, "6 to 30 minutes"),
    coded(3, "31 to 60 minutes"),
    coded(4, "After 60 minutes"),
    coded(5, "Varies / not usually in the morning"),
    coded(6, "Do not smoke in the morning"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
WORK_SCHEDULE = [
    coded(1, "A regular daytime schedule"),
    coded(2, "A regular evening shift"),
    coded(3, "A regular night shift"),
    coded(4, "A rotating shift"),
    coded(5, "Some other schedule"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
INCONTINENCE_FREQUENCY = [
    coded(1, "Every day"),
    coded(2, "A few times a week"),
    coded(3, "A few times a month"),
    coded(4, "A few times a year"),
    coded(5, "Never"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
LEAK_AMOUNT = [
    coded(1, "Drops"),
    coded(2, "Small splashes"),
    coded(3, "More"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
LEAK_EVENT_FREQUENCY = [
    coded(1, "Often"),
    coded(2, "Sometimes"),
    coded(3, "Rarely"),
    coded(4, "Never"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
ACTIVITY_AFFECT = [
    coded(1, "Not at all"),
    coded(2, "Slightly"),
    coded(3, "Moderately"),
    coded(4, "Quite a bit"),
    coded(5, "Extremely"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
NOCTURIA = [
    coded(0, "None"),
    coded(1, "1 time"),
    coded(2, "2 times"),
    coded(3, "3 times"),
    coded(4, "4 times"),
    coded(5, "5 or more times"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]
ARTHRITIS_TYPE = [
    coded(1, "Rheumatoid arthritis"),
    coded(2, "Osteoarthritis"),
    coded(3, "Psoriatic arthritis"),
    coded(4, "Other"),
    coded(7, "Refused"),
    coded(9, "Don't know"),
]


def field(
    field_id: str,
    label: str,
    *,
    nhanes_code: str | None = None,
    options: list[dict] | None = None,
    input_type: str = "coded_single_select",
    source: str | None = None,
    branch: dict | None = None,
    helper_only: bool = False,
    derives: list[str] | None = None,
) -> dict:
    item = {
        "field_id": field_id,
        "label": label,
        "input_type": input_type,
    }
    if nhanes_code:
        item["nhanes_code"] = nhanes_code
    if options is not None:
        item["options"] = options
    if source:
        item["source_url"] = source
    if branch:
        item["branch_if"] = branch
    if helper_only:
        item["helper_only"] = True
    if derives:
        item["derives"] = derives
    return item


QUESTION_GROUPS = [
    {
        "id": "core_profile",
        "title": "Core profile and general health",
        "questions": [
            {
                "id": "q_core_demo",
                "title": "Demographics and overall health",
                "fields": [
                    field("age_years", "Age in years", nhanes_code="RIDAGEYR", input_type="integer", source=SOURCES["DEMO"]),
                    field("gender", "Sex", nhanes_code="RIAGENDR", options=GENDER, source=SOURCES["DEMO"]),
                    field("education", "Education level", nhanes_code="DMDEDUC2", options=EDUCATION, source=SOURCES["DEMO"], branch={"age_years_min": 20}),
                    field("pregnancy_status", "Pregnancy status", nhanes_code="RIDEXPRG", options=PREGNANCY, source=SOURCES["DEMO"], branch={"gender_equals": 2, "age_years_min": 20, "age_years_max": 44}),
                    field("huq010___general_health_condition", "General health condition", nhanes_code="HUQ010", options=GENERAL_HEALTH, source=SOURCES["HUQ"], derives=["general_health_condition", "general_health"]),
                    field("huq051___#times_receive_healthcare_over_past_year", "Number of healthcare visits in the past year", nhanes_code="HUQ051", input_type="integer", source=SOURCES["HUQ"]),
                    field("huq071___overnight_hospital_patient_in_last_year", "Overnight hospital patient in the last year", nhanes_code="HUQ071", options=YES_NO, source=SOURCES["HUQ"], derives=["overnight_hospital", "hospitalized_lastyear"]),
                    field("med_count", "Number of prescription medicines currently taken", nhanes_code="RXDCOUNT", input_type="integer", helper_only=True),
                ],
            },
            {
                "id": "q_body_measures",
                "title": "Body measurements and optional checkup values",
                "fields": [
                    field("weight_kg", "Current weight (kg)", nhanes_code="BMXWT", input_type="number"),
                    field("waist_cm", "Waist circumference (cm)", nhanes_code="BMXWAIST", input_type="number"),
                    field("bmi", "BMI", nhanes_code="BMXBMI", input_type="number"),
                    field("sbp_mean", "Average systolic blood pressure", nhanes_code="BPXSY1-3", input_type="number", helper_only=True),
                    field("dbp_mean", "Average diastolic blood pressure", nhanes_code="BPXDI1-3", input_type="number", helper_only=True),
                ],
            },
        ],
    },
    {
        "id": "sleep_and_work",
        "title": "Sleep, fatigue, work schedule, and activity",
        "questions": [
            {
                "id": "q_sleep",
                "title": "Sleep symptoms and duration",
                "fields": [
                    field("slq030___how_often_do_you_snore?", "How often do you snore?", nhanes_code="SLQ030", options=SNORE_FREQUENCY, source=SOURCES["SLQ"]),
                    field("slq050___ever_told_doctor_had_trouble_sleeping?", "Ever told doctor you had trouble sleeping?", nhanes_code="SLQ050", options=YES_NO, source=SOURCES["SLQ"], derives=["told_dr_trouble_sleeping"]),
                    field("sld012___sleep_hours___weekdays_or_workdays", "Sleep hours on weekdays / workdays", nhanes_code="SLD012", input_type="number", source=SOURCES["SLQ"], derives=["sleep_hours_weekdays"]),
                    field("sld013___sleep_hours___weekends", "Sleep hours on weekends", nhanes_code="SLD013", input_type="number", source=SOURCES["SLQ"]),
                    field("dpq040___feeling_tired_or_having_little_energy", "Feeling tired or having little energy", nhanes_code="DPQ040", options=PHQ_FREQUENCY, source=SOURCES["DPQ"], derives=["feeling_tired_little_energy"]),
                ],
            },
            {
                "id": "q_work_activity",
                "title": "Work schedule and activity",
                "fields": [
                    field("ocq670___overall_work_schedule_past_3_months", "Overall work schedule in the past 3 months", nhanes_code="OCQ670", options=WORK_SCHEDULE, source=SOURCES["OCQ"], branch={"age_years_min": 16}, derives=["overall_work_schedule", "work_schedule"]),
                    field("ocq180___hours_worked_last_week_in_total_all_jobs", "Hours worked last week across all jobs", nhanes_code="OCQ180", input_type="integer", source=SOURCES["OCQ"], branch={"age_years_min": 16}, derives=["hours_worked_per_week"]),
                    field("pad680___minutes_sedentary_activity", "Minutes of sedentary activity per day", nhanes_code="PAD680", input_type="integer", source=SOURCES["OCQ"], derives=["sedentary_minutes"]),
                    field("paq620___moderate_work_activity", "Moderate work activity", nhanes_code="PAQ620", options=YES_NO, source=SOURCES["OCQ"]),
                    field("paq665___moderate_recreational_activities", "Moderate recreational activities", nhanes_code="PAQ665", options=YES_NO, source=SOURCES["OCQ"], derives=["moderate_recreational"]),
                    field("paq650___vigorous_recreational_activities", "Vigorous recreational activities", nhanes_code="PAQ650", options=YES_NO, source=SOURCES["OCQ"]),
                    field("paq605___vigorous_work_activity", "Vigorous work activity", nhanes_code="PAQ605", options=YES_NO, source=SOURCES["OCQ"], helper_only=True),
                ],
            },
        ],
    },
    {
        "id": "alcohol_smoking",
        "title": "Alcohol and smoking",
        "questions": [
            {
                "id": "q_alcohol",
                "title": "Alcohol use",
                "fields": [
                    field("alq111___ever_had_a_drink_of_any_kind_of_alcohol", "Ever had a drink of any kind of alcohol", nhanes_code="ALQ111", options=YES_NO, source=SOURCES["ALQ"]),
                    field("alq130___avg_#_alcoholic_drinks/day___past_12_mos", "Average number of alcoholic drinks per day in past 12 months", nhanes_code="ALQ130", input_type="number", source=SOURCES["ALQ"], derives=["avg_drinks_per_day"]),
                    field("alq151___ever_have_4/5_or_more_drinks_every_day?", "Ever have 4/5 or more drinks almost every day", nhanes_code="ALQ151", options=YES_NO, source=SOURCES["ALQ"]),
                    field("alq170_helper_times_4_5_drinks_one_occasion_30d", "Past 30 days: number of times 4/5+ drinks on one occasion", nhanes_code="ALQ170", input_type="integer", source=SOURCES["ALQ"], helper_only=True, derives=["ever_heavy_drinker", "alcohol_any_risk_signal"]),
                ],
            },
            {
                "id": "q_smoking",
                "title": "Smoking",
                "fields": [
                    field("smq020___smoked_at_least_100_cigarettes_in_life", "Smoked at least 100 cigarettes in life", nhanes_code="SMQ020", options=YES_NO, source=SOURCES["SMQ"]),
                    field("smq040___do_you_now_smoke_cigarettes?", "Do you now smoke cigarettes?", nhanes_code="SMQ040", options=SMOKE_NOW, source=SOURCES["SMQ"], derives=["smoking_now"], branch={"depends_on": "smq020___smoked_at_least_100_cigarettes_in_life", "show_if_values": [1]}),
                    field("smd650___avg_#_cigarettes/day_during_past_30_days", "Average cigarettes per day during past 30 days", nhanes_code="SMD650", input_type="integer", source=SOURCES["SMQ"], derives=["avg_cigarettes_per_day", "cigarettes_per_day"], branch={"depends_on": "smq040___do_you_now_smoke_cigarettes?", "show_if_values": [1, 2]}),
                    field("smq078___how_soon_after_waking_do_you_smoke", "How soon after waking do you smoke?", nhanes_code="SMQ078", options=TIME_TO_FIRST_CIG, source=SOURCES["SMQ"], branch={"depends_on": "smq040___do_you_now_smoke_cigarettes?", "show_if_values": [1, 2]}),
                ],
            },
        ],
    },
    {
        "id": "cardiometabolic_history",
        "title": "Cardiometabolic history and medications",
        "questions": [
            {
                "id": "q_bp",
                "title": "Blood pressure and cholesterol",
                "fields": [
                    field("bpq020___ever_told_you_had_high_blood_pressure", "Ever told you had high blood pressure", nhanes_code="BPQ020", options=YES_NO, source=SOURCES["BPQ"], derives=["ever_told_high_bp"]),
                    field("bpq030___told_had_high_blood_pressure___2+_times", "Told had high blood pressure 2 or more times", nhanes_code="BPQ030", options=YES_NO, source=SOURCES["BPQ"], branch={"depends_on": "bpq020___ever_told_you_had_high_blood_pressure", "show_if_values": [1]}),
                    field("bpq040a___taking_prescription_for_hypertension", "Taking prescription for hypertension", nhanes_code="BPQ040A", options=YES_NO, source=SOURCES["BPQ"], derives=["taking_bp_prescription"], branch={"depends_on": "bpq020___ever_told_you_had_high_blood_pressure", "show_if_values": [1]}),
                    field("bpq050a___now_taking_prescribed_medicine_for_hbp", "Now taking prescribed medicine for high blood pressure", nhanes_code="BPQ050A", options=YES_NO, source=SOURCES["BPQ"], branch={"depends_on": "bpq020___ever_told_you_had_high_blood_pressure", "show_if_values": [1]}),
                    field("bpq080___doctor_told_you___high_cholesterol_level", "Doctor told you high cholesterol level", nhanes_code="BPQ080", options=YES_NO, source=SOURCES["BPQ"], derives=["ever_told_high_cholesterol", "told_high_cholesterol"]),
                ],
            },
            {
                "id": "q_diabetes",
                "title": "Diabetes and related risk",
                "fields": [
                    field("diq010___doctor_told_you_have_diabetes", "Doctor told you have diabetes", nhanes_code="DIQ010", options=YES_NO_BORDERLINE, source=SOURCES["DIQ"], derives=["ever_told_diabetes", "diabetes"]),
                    field("diq050___taking_insulin_now", "Taking insulin now", nhanes_code="DIQ050", options=YES_NO, source=SOURCES["DIQ"], derives=["taking_insulin"], branch={"depends_on": "diq010___doctor_told_you_have_diabetes", "show_if_values": [1, 3]}),
                    field("diq070___take_diabetic_pills_to_lower_blood_sugar", "Take diabetic pills to lower blood sugar", nhanes_code="DIQ070", options=YES_NO, source=SOURCES["DIQ"], derives=["taking_diabetic_pills", "takes_diabetes_pills"], branch={"depends_on": "diq010___doctor_told_you_have_diabetes", "show_if_values": [1, 3]}),
                    field("mcq300c___close_relative_had_diabetes", "Close relative had diabetes", nhanes_code="MCQ300C", options=YES_NO, source=SOURCES["MCQ"]),
                ],
            },
            {
                "id": "q_conditions",
                "title": "Other medical conditions",
                "fields": [
                    field("mcq053___taking_treatment_for_anemia/past_3_mos", "Taking treatment for anemia in past 3 months", nhanes_code="MCQ053", options=YES_NO, source=SOURCES["MCQ"], derives=["taking_anemia_treatment"]),
                    field("mcq092___ever_receive_blood_transfusion", "Ever received blood transfusion", nhanes_code="MCQ092", options=YES_NO, source=SOURCES["MCQ"], derives=["ever_had_blood_transfusion", "blood_transfusion"]),
                    field("mcq160a___ever_told_you_had_arthritis", "Ever told you had arthritis", nhanes_code="MCQ160A", options=YES_NO, source=SOURCES["MCQ"], derives=["ever_told_arthritis"]),
                    field("mcq195___which_type_of_arthritis_was_it?", "Which type of arthritis was it?", nhanes_code="MCQ195", options=ARTHRITIS_TYPE, source=SOURCES["MCQ"], branch={"depends_on": "mcq160a___ever_told_you_had_arthritis", "show_if_values": [1]}),
                    field("mcq160b___ever_told_you_had_congestive_heart_failure", "Ever told you had congestive heart failure", nhanes_code="MCQ160B", options=YES_NO, source=SOURCES["MCQ"], derives=["ever_told_heart_failure", "heart_failure"]),
                    field("mcq160e___ever_told_you_had_heart_attack", "Ever told you had heart attack", nhanes_code="MCQ160E", options=YES_NO, source=SOURCES["MCQ"], derives=["ever_told_heart_attack"]),
                    field("mcq160f___ever_told_you_had_stroke", "Ever told you had stroke", nhanes_code="MCQ160F", options=YES_NO, source=SOURCES["MCQ"], derives=["ever_told_stroke"]),
                    field("mcq160l___ever_told_you_had_any_liver_condition", "Ever told you had any liver condition", nhanes_code="MCQ160L", options=YES_NO, source=SOURCES["MCQ"], derives=["liver_condition"]),
                    field("heq030___ever_told_you_have_hepatitis_c?", "Ever told you have hepatitis C", nhanes_code="HEQ030", options=YES_NO, source=SOURCES["HEQ"], derives=["ever_hepatitis_c"]),
                    field("mcq080___doctor_ever_said_you_were_overweight", "Doctor ever said you were overweight", nhanes_code="MCQ080", options=YES_NO, source=SOURCES["MCQ"], derives=["doctor_said_overweight"]),
                ],
            },
        ],
    },
    {
        "id": "urinary_kidney",
        "title": "Urinary and kidney symptoms",
        "questions": [
            {
                "id": "q_kidney_history",
                "title": "Kidney history",
                "fields": [
                    field("kiq022___ever_told_you_had_weak/failing_kidneys?", "Ever told you had weak or failing kidneys", nhanes_code="KIQ022", options=YES_NO, source=SOURCES["KIQ"], derives=["kidney_disease"]),
                    field("kiq026___ever_had_kidney_stones?", "Ever had kidney stones", nhanes_code="KIQ026", options=YES_NO, source=SOURCES["KIQ"], derives=["ever_had_kidney_stones"]),
                    field("kiq480___how_many_times_urinate_in_night?", "How many times do you urinate at night?", nhanes_code="KIQ480", options=NOCTURIA, source=SOURCES["KIQ"], derives=["times_urinate_in_night"]),
                ],
            },
            {
                "id": "q_leakage",
                "title": "Urinary leakage",
                "fields": [
                    field("kiq005___how_often_have_urinary_leakage?", "How often have urinary leakage?", nhanes_code="KIQ005", options=INCONTINENCE_FREQUENCY, source=SOURCES["KIQ"], derives=["how_often_urinary_leakage"]),
                    field("kiq010___how_much_urine_lose_each_time?", "How much urine do you lose each time?", nhanes_code="KIQ010", options=LEAK_AMOUNT, source=SOURCES["KIQ"], branch={"depends_on": "kiq005___how_often_have_urinary_leakage?", "show_if_values": [1, 2, 3, 4]}),
                    field("kiq042___leak_urine_during_physical_activities?", "Leak urine during physical activities?", nhanes_code="KIQ042", options=YES_NO, source=SOURCES["KIQ"], branch={"depends_on": "kiq005___how_often_have_urinary_leakage?", "show_if_values": [1, 2, 3, 4]}),
                    field("kiq430___how_frequently_does_this_occur?", "How frequently does leakage during physical activities occur?", nhanes_code="KIQ430", options=LEAK_EVENT_FREQUENCY, source=SOURCES["KIQ"], branch={"depends_on": "kiq042___leak_urine_during_physical_activities?", "show_if_values": [1]}),
                    field("kiq044___urinated_before_reaching_the_toilet?", "Urinated before reaching the toilet?", nhanes_code="KIQ044", options=YES_NO, source=SOURCES["KIQ"], derives=["urinated_before_toilet"], branch={"depends_on": "kiq005___how_often_have_urinary_leakage?", "show_if_values": [1, 2, 3, 4]}),
                    field("kiq450___how_frequently_does_this_occur?", "How frequently does this occur before reaching the toilet?", nhanes_code="KIQ450", options=LEAK_EVENT_FREQUENCY, source=SOURCES["KIQ"], branch={"depends_on": "kiq044___urinated_before_reaching_the_toilet?", "show_if_values": [1]}),
                    field("kiq052___how_much_were_daily_activities_affected?", "How much were daily activities affected?", nhanes_code="KIQ052", options=ACTIVITY_AFFECT, source=SOURCES["KIQ"], branch={"depends_on": "kiq005___how_often_have_urinary_leakage?", "show_if_values": [1, 2, 3, 4]}),
                ],
            },
        ],
    },
    {
        "id": "respiratory_pain",
        "title": "Breathing, asthma, and abdominal pain",
        "questions": [
            {
                "id": "q_breathing_asthma",
                "title": "Breathing and asthma",
                "fields": [
                    field("cdq010___shortness_of_breath_on_stairs/inclines", "Shortness of breath on stairs or inclines", nhanes_code="CDQ010", options=YES_NO, source=SOURCES["CDQ"], derives=["cdq010_sob_stairs"], branch={"age_years_min": 40}),
                    field("mcq010___ever_been_told_you_have_asthma", "Ever been told you have asthma", nhanes_code="MCQ010", options=YES_NO, source=SOURCES["MCQ"]),
                    field("mcq040___had_asthma_attack_in_past_year", "Had asthma attack in past year", nhanes_code="MCQ040", options=YES_NO, source=SOURCES["MCQ"], branch={"depends_on": "mcq010___ever_been_told_you_have_asthma", "show_if_values": [1]}),
                ],
            },
            {
                "id": "q_pain",
                "title": "Abdominal pain",
                "fields": [
                    field("mcq520___abdominal_pain_during_past_12_months?", "Abdominal pain during past 12 months", nhanes_code="MCQ520", options=YES_NO, source=SOURCES["MCQ"], derives=["abdominal_pain"]),
                    field("mcq540___ever_seen_a_dr_about_this_pain", "Ever seen a doctor about this pain", nhanes_code="MCQ540", options=YES_NO, source=SOURCES["MCQ"], derives=["saw_dr_for_pain"], branch={"depends_on": "mcq520___abdominal_pain_during_past_12_months?", "show_if_values": [1]}),
                ],
            },
        ],
    },
    {
        "id": "female_reproductive",
        "title": "Female reproductive and hormone questions",
        "branch_if": {"gender_equals": 2},
        "questions": [
            {
                "id": "q_reproductive_history",
                "title": "Periods, pregnancy, hormones",
                "fields": [
                    field("rhq031___had_regular_periods_in_past_12_months", "Had regular periods in the past 12 months", nhanes_code="RHQ031", options=YES_NO, source=SOURCES["RHQ"], derives=["regular_periods"], branch={"age_years_min": 20, "age_years_max": 59}),
                    field("rhq060___age_at_last_menstrual_period", "Age at last menstrual period", nhanes_code="RHQ060", input_type="integer", source=SOURCES["RHQ"], branch={"age_years_min": 20, "age_years_max": 59}),
                    field("rhq540___ever_use_female_hormones?", "Ever use female hormones", nhanes_code="RHQ540", options=YES_NO, source=SOURCES["RHQ"], derives=["rhq540_ever_hormones"], branch={"age_years_min": 20}),
                    field("rhq131___ever_been_pregnant?", "Ever been pregnant", nhanes_code="RHQ131", options=YES_NO, source=SOURCES["RHQ"], branch={"age_years_min": 20, "age_years_max": 59}),
                    field("rhq160___how_many_times_have_been_pregnant?", "How many times have been pregnant", nhanes_code="RHQ160", input_type="integer", source=SOURCES["RHQ"], branch={"depends_on": "rhq131___ever_been_pregnant?", "show_if_values": [1]}),
                ],
            },
        ],
    },
    {
        "id": "weight_and_prevention",
        "title": "Weight preference and preventive advice",
        "questions": [
            {
                "id": "q_weight_preference",
                "title": "Weight preference",
                "fields": [
                    field("whq040___like_to_weigh_more,_less_or_same", "Would like to weigh more, less, or stay about the same", nhanes_code="WHQ040", options=WEIGHT_PREFERENCE, source=SOURCES["WHQ"]),
                    field("whq070___tried_to_lose_weight_in_past_year", "Tried to lose weight in past year", nhanes_code="WHQ070", options=YES_NO, source=SOURCES["WHQ"], derives=["tried_to_lose_weight"]),
                    field("mcq366d___doctor_told_to_reduce_fat_in_diet", "Doctor told to reduce fat in diet", nhanes_code="MCQ366D", options=YES_NO, source=SOURCES["MCQ"]),
                ],
            },
        ],
    },
    {
        "id": "optional_labs",
        "title": "Optional recent checkup and lab values",
        "questions": [
            {
                "id": "q_checkup_values",
                "title": "Optional values from recent labs or checkup",
                "help_text": "These are not NHANES questionnaire questions, but they are needed to populate some production model columns. Leave blank if unknown; the mapper will create missingness flags automatically.",
                "fields": [
                    field("total_cholesterol_mg_dl", "Total cholesterol (mg/dL)", input_type="number", helper_only=True),
                    field("hdl_cholesterol_mg_dl", "HDL cholesterol (mg/dL)", input_type="number", helper_only=True),
                    field("ldl_cholesterol_mg_dl", "LDL cholesterol (mg/dL)", input_type="number", helper_only=True),
                    field("triglycerides_mg_dl", "Triglycerides (mg/dL)", input_type="number", helper_only=True),
                    field("fasting_glucose_mg_dl", "Fasting glucose (mg/dL)", input_type="number", helper_only=True),
                    field("glucose_mg_dl", "Glucose (mg/dL)", input_type="number", helper_only=True),
                    field("uacr_mg_g", "Urine albumin-creatinine ratio (mg/g)", input_type="number", helper_only=True),
                    field("total_protein_g_dl", "Total protein (g/dL)", input_type="number", helper_only=True),
                    field("wbc_1000_cells_ul", "White blood cell count (1000 cells/uL)", input_type="number", helper_only=True),
                ],
            },
        ],
    },
]


DERIVED_FEATURES = [
    {"feature": "gender_female", "rule": "1 if gender == 2 else 0 if gender is known else null"},
    {"feature": "general_health_condition", "rule": "Alias of HUQ010"},
    {"feature": "general_health", "rule": "Alias of HUQ010"},
    {"feature": "told_dr_trouble_sleeping", "rule": "Alias of SLQ050"},
    {"feature": "sleep_hours_weekdays", "rule": "Alias of SLD012"},
    {"feature": "avg_drinks_per_day", "rule": "Alias of ALQ130"},
    {"feature": "ever_heavy_drinker", "rule": "1 if ALQ151 == 1 or ALQ170 helper > 0; 0 if both available and negative; null otherwise"},
    {"feature": "alcohol_any_risk_signal", "rule": "1 if any alcohol-risk signal is present from ALQ111/130/151/170 helper; 0 if all known and negative; null otherwise"},
    {"feature": "smoking_now", "rule": "1 if SMQ040 in {1,2}; 0 if SMQ040 == 3; null otherwise"},
    {"feature": "cigarettes_per_day", "rule": "Alias of SMD650"},
    {"feature": "avg_cigarettes_per_day", "rule": "Alias of SMD650"},
    {"feature": "moderate_recreational", "rule": "Alias of PAQ665"},
    {"feature": "moderate_exercise", "rule": "1 if PAQ620 == 1 or PAQ665 == 1; 0 if both known and neither yes; null otherwise"},
    {"feature": "vigorous_exercise", "rule": "1 if PAQ605 helper == 1 or PAQ650 == 1; 0 if both known and neither yes; null otherwise"},
    {"feature": "work_schedule", "rule": "Alias of OCQ670"},
    {"feature": "overall_work_schedule", "rule": "Alias of OCQ670"},
    {"feature": "hours_worked_per_week", "rule": "Alias of OCQ180"},
    {"feature": "doctor_said_overweight", "rule": "Alias of MCQ080"},
    {"feature": "ever_told_high_cholesterol", "rule": "Alias of BPQ080"},
    {"feature": "told_high_cholesterol", "rule": "Alias of BPQ080"},
    {"feature": "ever_told_diabetes", "rule": "Alias of DIQ010"},
    {"feature": "diabetes", "rule": "Alias of DIQ010"},
    {"feature": "taking_insulin", "rule": "Alias of DIQ050"},
    {"feature": "taking_diabetic_pills", "rule": "Alias of DIQ070"},
    {"feature": "takes_diabetes_pills", "rule": "Alias of DIQ070"},
    {"feature": "taking_bp_prescription", "rule": "Alias of BPQ040A"},
    {"feature": "ever_told_high_bp", "rule": "Alias of BPQ020"},
    {"feature": "times_urinate_in_night", "rule": "Alias of KIQ480"},
    {"feature": "how_often_urinary_leakage", "rule": "Alias of KIQ005"},
    {"feature": "urinated_before_toilet", "rule": "Alias of KIQ044"},
    {"feature": "ever_had_kidney_stones", "rule": "Alias of KIQ026"},
    {"feature": "kidney_disease", "rule": "Alias of KIQ022"},
    {"feature": "taking_anemia_treatment", "rule": "Alias of MCQ053"},
    {"feature": "ever_had_blood_transfusion", "rule": "Alias of MCQ092"},
    {"feature": "blood_transfusion", "rule": "Alias of MCQ092"},
    {"feature": "ever_told_arthritis", "rule": "Alias of MCQ160A"},
    {"feature": "ever_told_heart_failure", "rule": "Alias of MCQ160B"},
    {"feature": "heart_failure", "rule": "Alias of MCQ160B"},
    {"feature": "ever_told_heart_attack", "rule": "Alias of MCQ160E"},
    {"feature": "ever_told_stroke", "rule": "Alias of MCQ160F"},
    {"feature": "liver_condition", "rule": "Alias of MCQ160L"},
    {"feature": "regular_periods", "rule": "Alias of RHQ031"},
    {"feature": "overnight_hospital", "rule": "Alias of HUQ071"},
    {"feature": "hospitalized_lastyear", "rule": "Alias of HUQ071"},
    {"feature": "cdq010_sob_stairs", "rule": "Alias of CDQ010"},
    {"feature": "abdominal_pain", "rule": "Alias of MCQ520"},
    {"feature": "saw_dr_for_pain", "rule": "Alias of MCQ540"},
    {"feature": "*_miss", "rule": "Auto-generated as 1 when the corresponding base feature is null/blank, else 0"},
]


MODEL_MAPPING_NOTES = [
    "The questionnaire uses NHANES-coded answers where official categories exist; optional checkup fields are included for model-required numeric inputs that are not NHANES questionnaire variables.",
    "The frontend should send a flat dictionary keyed by field_id.",
    "The transformer script should create all alias columns and *_miss flags automatically.",
    "Perimenopause replaces the older menopause label.",
]


data = {
    "metadata": {
        "name": "NHANES Combined Question Flow v2",
        "version": "2.0.0",
        "generated_on": "2026-03-19",
        "description": "Branching questionnaire aligned to the current HalfFull screening feature summary and model-runner contract.",
        "frontend_answer_contract": "Submit a flat dictionary keyed by field_id. Values should be the NHANES numeric codes for coded questions, or numbers for numeric entry questions.",
        "conditions_covered": [
            "thyroid",
            "kidney",
            "sleep_disorder",
            "anemia",
            "liver",
            "prediabetes",
            "inflammation",
            "electrolytes",
            "hepatitis",
            "perimenopause",
            "iron_deficiency",
        ],
        "sources": SOURCES,
        "notes": MODEL_MAPPING_NOTES,
    },
    "question_groups": QUESTION_GROUPS,
    "derived_features": DERIVED_FEATURES,
}

OUT_JSON.write_text(json.dumps(data, indent=2))

notes = [
    "# NHANES Combined Question Flow v2",
    "",
    "This file was rebuilt around the latest feature summary and production model-runner targets.",
    "",
    "## What changed",
    "",
    "- Questions are grouped logically: profile, sleep/work, alcohol/smoking, cardiometabolic history, urinary/kidney, respiratory/pain, female reproductive, weight/prevention, and optional checkup values.",
    "- Branches are defined where the frontend can skip irrelevant questions, for example non-female reproductive items, asthma-attack follow-ups only after asthma, and urinary follow-ups only after leakage.",
    "- `_miss` features are not user-entered. They are intended to be created automatically by the transformer from whether the base field is present.",
    "- Optional recent-checkup fields are included because several production models expect raw numeric inputs such as cholesterol, glucose, UACR, WBC, or blood pressure values in addition to questionnaire variables.",
    "",
    "## Source set",
    "",
]
for key, url in SOURCES.items():
    notes.append(f"- {key}: {url}")
notes.append("")
notes.append("## Important implementation note")
notes.append("")
notes.append("- Production inflammation scoring should use `models/inflammation_lr_l1_45feat.joblib`. Its metadata contains 46 input columns because one coefficient was zeroed out, but the saved production artifact is the 45-feature L1 model.")
notes.append("")

OUT_MD.write_text("\n".join(notes))

print(f"Wrote {OUT_JSON}")
print(f"Wrote {OUT_MD}")
