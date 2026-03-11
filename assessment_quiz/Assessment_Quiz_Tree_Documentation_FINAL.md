# HalfFull Assessment Quiz Tree
## Comprehensive Design Documentation (v1.1 - Hybrid Lab Path)

---

## 1. OVERVIEW

The **Assessment Quiz Tree** is the foundation of HalfFull's diagnostic pipeline. It structures an intelligent questionnaire with **three distinct pathways**:

### Three Assessment Paths:
1. **No Labs Path** (22 questions) - Full symptom-based assessment → NHANES rule-based scoring
2. **Hybrid Labs Path** (10-12 questions) - Lab upload + critical symptom questions → Hybrid scoring
3. **Optional Full Path** - User choice to do complete assessment even with labs

The assessment:
- **Collects data efficiently** - Users with labs skip redundant questions
- **Routes dynamically** - Conditional logic based on answers + lab status
- **Maps each answer to ML features** that feed into scoring and classification
- **Recognizes non-lab pathologies** - Post-exertional malaise, depression, sleep disorders (not visible in labs)
- **Maintains complete traceability** from question → feature → score

**Key Innovation**: Uses lab results (when available) to inform hybrid scoring, while still capturing non-lab pathologies that are critical for accurate diagnosis.

---

## 2. THE THREE ASSESSMENT PATHS

### Decision Tree:

```
START
│
├─ Q0.0 "Do you have recent lab results (last 6 months)?"
│  │
│  ├─ YES → Q0.1: Lab Upload (OCR)
│  │  │
│  │  ├─ Extract: Ferritin, TSH, B12, Hemoglobin, etc.
│  │  │
│  │  └─ HYBRID PATH (10-12 questions):
│  │     ├─ Q1.1-Q1.5 (Sleep) → SHOW (labs don't cover sleep disorders)
│  │     ├─ Q2.1-Q2.5 (Nutrition) → SKIP (have ferritin/B12 from labs)
│  │     ├─ Q3.1-Q3.6 (Hormonal) → SKIP (have TSH from labs)
│  │     ├─ Q4.1-Q4.5 (Activity) → SHOW (PEM/ME/CFS not in labs)
│  │     ├─ Q5.1-Q5.5 (Mental) → SHOW (depression/anxiety not in labs)
│  │     └─ → HYBRID SCORING (lab + symptom patterns)
│  │
│  └─ NO → FULL PATH (22 questions)
│     ├─ Q1.1-Q1.5 (Sleep)
│     ├─ Q2.1-Q2.5 (Nutrition)
│     ├─ Q3.1-Q3.6 (Hormonal)
│     ├─ Q4.1-Q4.5 (Activity)
│     ├─ Q5.1-Q5.5 (Mental)
│     └─ → NHANES RULE-BASED SCORING
│
└─ RESULTS: Ranked fatigue drivers + doctor PDF
```

### Path Comparison Table:

| Aspect | No Labs (Full) | Has Labs (Hybrid) |
|--------|---|---|
| **Total Questions** | 22 | 10-12 |
| **Completion Time** | 12-15 min | 7-10 min |
| **Sleep Module** | ✅ Full (Q1.1-Q1.5) | ✅ Full (Q1.1-Q1.5) |
| **Nutrition Module** | ✅ Full (Q2.1-Q2.5) | ❌ Skipped (have ferritin/B12) |
| **Hormonal Module** | ✅ Full (Q3.1-Q3.6) | ❌ Skipped (have TSH) |
| **Activity Module** | ✅ Full (Q4.1-Q4.5) | ✅ Full (Q4.1-Q4.5) |
| **Mental Health Module** | ✅ Full (Q5.1-Q5.5) | ✅ Full (Q5.1-Q5.5) |
| **Can Detect ME/CFS** | ✅ Yes (Q4.3 PEM) | ✅ Yes (Q4.3 PEM) |
| **Can Detect Depression** | ✅ Yes (Q5.2-Q5.3) | ✅ Yes (Q5.2-Q5.3) |
| **Can Detect Sleep Disorders** | ✅ Yes (Q1.2-Q1.3) | ✅ Yes (Q1.2-Q1.3) |
| **Data Source** | Symptoms only | Labs + symptoms |
| **Scoring Type** | NHANES rule-based | Hybrid (lab + symptom) |

### Why This Design?

**The Critical Insight**: Not everything related to fatigue appears in blood work.

**Non-Lab Pathologies We Must Still Detect**:
- **Post-exertional malaise** - Hallmark of ME/CFS, no lab marker exists
- **Sleep disorders** - Insomnia, sleep apnea, restless legs can have normal labs
- **Depression & anxiety** - Not measured in standard blood work panels
- **Functional impairment** - The severity proxy that determines urgency

**Example Scenario**:
```
User uploads labs:
├─ Ferritin: 45 ng/mL (NORMAL ✓)
├─ TSH: 2.1 mIU/L (NORMAL ✓)
└─ B12: 350 pg/mL (NORMAL ✓)

If we SKIP mental health questions:
└─ Result: "All labs normal → no problem" ❌ WRONG

If we ASK mental health questions:
├─ Q5.2: Mood = "Depressed"
├─ Q5.1: Anxiety = "Often"
└─ Result: "Depression with normal labs" ✅ CORRECT

Therefore: Hybrid path is smarter than either path alone.
```

---

## 3. MODULE 0: PRE-ASSESSMENT (LAB GATE)

This module determines which of the three paths the user takes.

### Q0.0: Lab Status Gate

**Purpose**: Determine if user has recent lab results and qualify for hybrid path.

| Attribute | Value |
|-----------|-------|
| Question | "Do you have recent lab results (from the last 6 months)?" |
| Help Text | "If you've had blood work done recently, you can upload it and we'll analyze it immediately. This will speed up your assessment. If not, no worries—we'll guide you on which tests you need." |
| Question Type | Binary (Yes / No) |
| Feature Name | `has_recent_labs` |
| Data Type | Boolean |
| **Options** | • **Yes, I have recent labs** → Route to Q0.1 (Lab Upload) |
| | • **No, I don't have recent labs** → Route to Q1.1 (Full Assessment) |
| Routing Logic | YES: Skip nutrition/hormonal modules, show lab upload + selective questions |
| | NO: Show full 22-question assessment |
| ML Feature | Binary flag; used to select scoring algorithm (hybrid vs. NHANES) |
| Validation | Required field (cannot skip) |

**Rationale**: Single binary gate that makes the system intelligent. Users see the path that matches their data. No wasted time on redundant questions when labs are available.

---

### Q0.1: Lab Upload & OCR Extraction

**Purpose**: Collect lab results for parsing and hybrid scoring.

| Attribute | Value |
|-----------|-------|
| **Step** | File Upload (shown only if Q0.0 = "Yes") |
| **Input Type** | File upload (PDF, JPG, PNG) |
| **Processing** | OCR extraction (Tesseract.js in Week 2; manual entry fallback in Week 1) |
| **Feature Name** | `uploaded_lab_values` |
| **Data Type** | Dict of extracted lab values with metadata |
| **Extracted Biomarkers** | • Ferritin (ng/mL, normal 30-400) |
| | • TSH (mIU/L, normal 0.4-4.5) |
| | • Free T4 (pg/mL, normal 0.8-1.8) |
| | • Hemoglobin (g/dL, normal 12-16 female, 13.5-17.5 male) |
| | • Hematocrit (%, normal 36-46) |
| | • Vitamin B12 (pg/mL, normal 200-900) |
| | • Folate (ng/mL, normal 5.4-16.0) |
| | • Vitamin D (ng/mL, normal 30-100) |
| | • Serum Iron (μg/dL, normal 60-170) |
| | • TIBC (μg/dL, normal 250-425) |
| **Status Encoding** | Each value tagged: LOW / NORMAL / HIGH |
| **Fallback Input** | Manual entry fields if OCR fails (Week 1 MVP) |
| **Validation** | File format, file size <10MB, basic OCR quality check |

**Example Extracted Output**:
```json
{
  "lab_upload_date": "2026-03-01",
  "labs": {
    "ferritin": {
      "value": 18,
      "unit": "ng/mL",
      "status": "low",
      "normal_range": { "min": 30, "max": 400 },
      "severity": "high"
    },
    "tsh": {
      "value": 2.5,
      "unit": "mIU/L",
      "status": "normal",
      "normal_range": { "min": 0.4, "max": 4.5 }
    },
    "hemoglobin": {
      "value": 11.5,
      "unit": "g/dL",
      "status": "low",
      "normal_range": { "min": 12, "max": 16 },
      "severity": "high"
    }
  }
}
```

**Routing Logic After Lab Extraction**:
```
After successful lab parse:
│
├─ If critical abnormalities found (ferritin <20, TSH >5, Hgb <10):
│  └─ Flag for high-priority pathway
│
├─ Show Q1.1-Q1.5 (Sleep - labs don't assess sleep quality/disorders)
├─ SKIP Q2.1-Q2.5 (Nutrition - we have ferritin, B12, folate)
├─ SKIP Q3.1-Q3.6 (Hormonal - we have TSH, free T4)
├─ Show Q4.1-Q4.5 (Activity - PEM/post-viral not in standard labs)
├─ Show Q5.1-Q5.5 (Mental - depression/anxiety not in labs)
│
└─ Proceed to hybrid scoring (see Section 9)
```

---

## 4. THE 5 CORE MODULES AT A GLANCE

| Module | Purpose | Key Questions | Critical Feature | Data Source |
|--------|---------|---|---|---|
| **SLEEP** | Sleep quality & disorders | Q1.1-Q1.5 | `sleep_quality_score` | Symptom-based |
| **NUTRITION** | Deficiency risk (iron, B12) | Q2.1-Q2.5 | `iron_deficiency_risk` | Labs (if available) + symptom |
| **HORMONAL** | Thyroid, cycle, stress | Q3.1-Q3.6 | `thyroid_history` | Labs (if available) + symptom |
| **ACTIVITY** | Exercise patterns, PEM | Q4.1-Q4.5 | `post_exertional_malaise` | Symptom-based (NOT in labs) |
| **MENTAL HEALTH** | Mood, anxiety, severity | Q5.1-Q5.5 | `fatigue_functional_impairment` | Symptom-based (NOT in labs) |

---

## 5. DETAILED MODULE SPECIFICATIONS

### MODULE 1: SLEEP (5 questions, 2-3 conditional)

**Purpose**: Assess sleep duration, quality, and identify specific sleep disorders that cause fatigue.

**Why shown in BOTH paths**: Sleep disorders (insomnia, sleep apnea, restless legs) can occur with completely normal lab values. Labs don't measure sleep quality.

| Q# | Question | Type | Feature | Conditional | Routing Logic |
|----|----------|------|---------|---|---|
| **Q1.1** | How many hours did you sleep last night? | Categorical | `sleep_hours_category` | No | Always → Q1.2 |
| **Q1.2** | How would you rate your sleep quality? | Numeric (1-10) | `sleep_quality_score` | No | If <5 → deepen inquiry |
| **Q1.3** | How often do you wake up at night? | Ordinal | `sleep_disruption_freq` | If Q1.2 <5 | If Often/Very Often → Q1.5 |
| **Q1.4** | Sleep issues (restless legs, nightmares, teeth grinding)? | Multi-select | `sleep_issues_flags` | If Q1.2 <5 | Each flag → different LLM follow-up |
| **Q1.5** | [CONDITIONAL] Restless legs duration? | Categorical | `restless_legs_duration` | If Q1.4 includes RLS | Iron pathway trigger |

**Data Pipeline**:
```
Q1.1 → sleep_hours_category [ordinal 0-3]
Q1.2 → sleep_quality_score [numeric 1-10]
Q1.3 → sleep_disruption_freq [ordinal 0-4]
Q1.4 → sleep_issues_flags [one-hot encoded]
       + restless_legs_flag → triggers iron pathway
Q1.5 → restless_legs_duration [months]
```

**Week 1 MVP**: Hardcode all 5 questions in JSON. No LLM follow-ups yet.
**Week 2**: LLM generates personalized follow-up based on Q1.4 flags.
**Week 3**: Include wearable sleep data if available (Apple Watch HRV, Oura ring).

---

### MODULE 2: NUTRITION (5 questions, 1-2 conditional)

**Purpose**: Identify dietary deficiency risk (iron, B12, vitamin D) that explains fatigue.

**Shown in**: NO LABS PATH ONLY (skipped if user has labs with ferritin/B12 values)

| Q# | Question | Type | Feature | Conditional | Routing Logic |
|----|----------|------|---------|---|---|
| **Q2.1** | Dietary restrictions? | Multi-select | `dietary_restrictions` | No | Vegans → iron/B12 focus |
| **Q2.2** | Iron deficiency diagnosis? | Categorical | `iron_history` | No | Yes → Q2.3 |
| **Q2.3** | [CONDITIONAL] Heavy menstrual bleeding? | Categorical | `heavy_menstrual_bleeding` | If Q2.2=Yes | Only if female (Q3.1) |
| **Q2.4** | Iron-rich food frequency? | Ordinal | `iron_food_frequency` | No | Rarely/Never → ↑ risk |
| **Q2.5** | Digestive issues (IBS, Crohn's)? | Binary | `gut_absorption_issues` | No | Yes → malabsorption |

**Why Skip in Hybrid Path**: We have ferritin and B12 directly from labs. These questions are predictive for people WITHOUT labs.

**Data Pipeline**:
```
Q2.1 → dietary_restrictions [one-hot]
       + vegan_flag → prioritize B12/iron
Q2.2 → iron_history [binary]
Q2.3 → heavy_menstrual_bleeding [binary, females only]
Q2.4 → iron_food_frequency [ordinal 0-4]
Q2.5 → gut_absorption_issues [binary]
```

---

### MODULE 3: HORMONAL (6 questions, 3-4 conditional)

**Purpose**: Screen for thyroid dysfunction, hormonal imbalances, and stress-related fatigue.

**Shown in**: NO LABS PATH ONLY (skipped if user has labs with TSH/T4 values)

| Q# | Question | Type | Feature | Conditional | Routing Logic |
|----|----------|------|---------|---|---|
| **Q3.1** | Biological sex? | Categorical | `biological_sex` | No | Determines pathway |
| **Q3.2** | [CONDITIONAL] Menstruation status? | Categorical | `menstrual_status` | If Q3.1=Female | Only female |
| **Q3.3** | [CONDITIONAL] Last menstrual period date? | Date | `last_menstrual_date` | If Q3.2=Yes | Calc cycle phase |
| **Q3.4** | Thyroid diagnosis? | Categorical | `thyroid_history` | No | Yes → Q3.5 |
| **Q3.5** | [CONDITIONAL] Thyroid medication adherence? | Categorical | `thyroid_medication_adherence` | If Q3.4≠None | Only if diagnosed |
| **Q3.6** | Recent major life stress? | Binary | `recent_stress` | No | Yes → cortisol pathway |

**Why Skip in Hybrid Path**: We have TSH/Free T4 directly from labs. These questions are predictive without lab data.

---

### MODULE 4: ACTIVITY (5 questions, 0-1 conditional)

**Purpose**: Assess exercise patterns and post-exertional malaise (ME/CFS indicator).

**Shown in**: BOTH PATHS (activity patterns and PEM are NOT in blood work)

| Q# | Question | Type | Feature | Conditional | Routing Logic |
|----|----------|------|---------|---|---|
| **Q4.1** | Activity level? | Ordinal | `activity_level` | No | Baseline metabolic |
| **Q4.2** | Exercise frequency per week? | Ordinal | `exercise_frequency` | No | High + fatigue → overtraining |
| **Q4.3** | Post-exertional malaise? | Categorical | `post_exertional_malaise` | No | **YES → ME/CFS pathway** |
| **Q4.4** | Fatigue onset timing after activity? | Categorical | `fatigue_onset_timing` | No | Timing → etiology |
| **Q4.5** | Recent infection/illness? | Categorical | `recent_infection` | No | YES → post-viral |

**Data Pipeline**:
```
Q4.3 → post_exertional_malaise [binary]
       if TRUE: me_cfs_pathway = HIGH (even with normal labs!)
Q4.4 → fatigue_onset_timing [categorical]
       Immediate → metabolic
       Next day → immune-mediated
```

**Critical Note**: This module is NOT skipped in hybrid path because PEM (post-exertional malaise) is NOT detectable in blood work. Users can have completely normal labs but ME/CFS.

---

### MODULE 5: MENTAL HEALTH (5 questions, 1 conditional)

**Purpose**: Screen for depression using validated Patient Health Questionnaire (PHQ-9) items from NHANES, and quantify functional impairment.

**Shown in**: BOTH PATHS (depression/anxiety are NOT in blood work)

**Data Source**: NHANES Patient Health Questionnaire (DPQ010-DPQ100, n=8,965 respondents)

| Q# | Question | Type | Feature | DPQ Item | Prevalence | Routing Logic |
|----|----------|------|---------|---|---|---|
| **Q5.1** | Little interest or pleasure in activities? | Ordinal | `anhedonia_frequency` | DPQ010 | 25.8% any, 9.1% significant | Anhedonia → MDD pathway |
| **Q5.2** | Feeling down, depressed, or hopeless? | Ordinal | `depressed_mood_frequency` | DPQ020 | 25.5% any, 7.9% significant | Depressed mood → MDD pathway |
| **Q5.3** | Trouble sleeping or sleeping too much? | Ordinal | `sleep_disturbance_frequency` | DPQ030 | 39.5% any, 21% significant | Sleep issues → Module 1 link |
| **★ Q5.4** | **Feeling tired or low energy? (KEY QUESTION)** | Ordinal | `fatigue_frequency_dpq` | DPQ040 | **49.9% any, 17.5% significant** | **THE CRITICAL FATIGUE QUESTION** |
| **Q5.5** | [CONDITIONAL] Impact on work/home activities? | Ordinal | `functional_impairment_dpq` | DPQ100 | 26.5% any, 5.1% significant | Severity quantifier |

### **CRITICAL DATA: Q5.4 (DPQ040) Fatigue in NHANES**

This is your key finding. The data shows:
- **Total reporting fatigue (score 1-3)**: 4,141 of 8,305 valid responses = **49.9%**
- **Daily fatigue (score 3)**: 697 respondents = **8.4%**
- **Several days/week (score 2)**: 754 respondents = **9.1%**
- **Combined (≥2 frequency)**: 1,451 respondents = **17.5% with significant, regular fatigue**

This is extraordinarily high. Almost **1 in 2 Americans report some level of fatigue**. Nearly **1 in 5 report it regularly (several days or daily)**.

### **All DPQ Items Prevalence Summary**:

| DPQ Item | Question | Any Symptoms | Daily | Several Days | Combined Significant |
|----------|----------|---|---|---|---|
| DPQ010 | Little interest/pleasure | 25.8% (2,142) | 3.7% (310) | 5.4% (450) | 9.1% (760) |
| DPQ020 | Feeling down/depressed | 25.5% (2,119) | 3.2% (269) | 4.7% (387) | 7.9% (656) |
| DPQ030 | Sleep issues | 39.5% (3,283) | 9.2% (764) | 7.5% (621) | 21% (1,385) |
| **DPQ040** | **Feeling tired/low energy** | **49.9% (4,141)** | **8.4% (697)** | **9.1% (754)** | **17.5% (1,451)** |
| DPQ050 | Poor appetite | 25.8% (2,140) | 4.5% (377) | 5.6% (464) | 9.1% (841) |
| DPQ060 | Feeling bad about yourself | 17.1% (1,423) | 2.5% (207) | 2.9% (239) | 5.4% (446) |
| DPQ070 | Trouble concentrating | 17.4% (1,442) | 3.5% (291) | 3.1% (254) | 6.6% (545) |
| DPQ080 | Moving/speaking slowly | 10.6% (882) | 1.8% (148) | 2.4% (196) | 4.2% (344) |
| DPQ090 | Thought of hurting yourself | 3.9% (326) | 0.4% (36) | 0.6% (51) | 1% (87) |
| DPQ100 | Difficulty with activities | 26.5% (1,466) | 1.3% (71) | 3.8% (209) | 5.1% (280) |

### **PHQ-9 Total Score (All Items Combined)**:
- **Overall probable depression (PHQ-9 ≥10)**: 912 respondents (10.2%)
- This aligns with CDC epidemiological estimates of 8-10% major depression prevalence

### **Why Q5.4 is THE Critical Question**:

1. **Fatigue is the #1 symptom** driving users to the app (49.9% prevalence)
2. **Q5.4 is the gateway to MDD screening** - nearly everyone experiences fatigue when depressed
3. **Q5.4 + Q5.5 together create the SEVERITY PROXY** - no lab test measures depression severity, but functional impact does
4. **Depression is 25%+ of fatigue cases** - if you miss this, you miss 1 in 4 users
5. **Not measurable in blood** - Only symptom-based screening works. This is why it's NEVER skipped.

**Critical Note**: Q5.4 (Fatigue) is the single most important question in the entire tree. It bridges depression and fatigue diagnostically. Nearly 50% report it. Combined with Q5.5 (functional impact), this creates the SEVERITY PROXY independent of any labs.

---

## 6. FEATURE ENGINEERING: RAW → ENGINEERED

### Raw Features (23 total from Q0.0-Q5.5):

```
has_recent_labs [binary]
uploaded_lab_values [dict of floats]
sleep_hours_category
sleep_quality_score
sleep_disruption_freq
sleep_issues_flags
restless_legs_duration
dietary_restrictions
iron_history
heavy_menstrual_bleeding
iron_food_frequency
gut_absorption_issues
biological_sex
menstrual_status
last_menstrual_date
thyroid_history
thyroid_medication_adherence
recent_stress
activity_level
exercise_frequency
post_exertional_malaise
fatigue_onset_timing
recent_infection
anxiety_frequency
mood_state
anhedonia_flag
fatigue_functional_impairment [CRITICAL]
daily_disability_percent
```

### Engineered Features (15 derived for scoring):

```
1. iron_deficiency_risk = f(iron_history, heavy_menstrual_bleeding, 
                             iron_food_frequency, vegan_flag)
                       OR = ferritin_level [if labs]
                       
2. b12_deficiency_risk = f(vegan_flag, vegetarian_flag, gut_absorption)
                      OR = b12_level [if labs]
                      
3. sleep_disorder_score = f(sleep_quality, sleep_disruption, sleep_issues)
                       (NOT replaced by labs - not measured in blood)
                       
4. thyroid_risk_score = f(thyroid_history, medication_adherence)
                     OR = tsh_level [if labs]
                     
5. post_exertional_malaise_flag = Q4.3 [binary]
                                (NOT in labs!)
                                
6. me_cfs_risk = f(post_exertional_malaise, recent_infection, 
                   fatigue_onset_timing)
              (NOT in labs!)
              
7. anxiety_risk = anxiety_frequency [ordinal 0-4]
               (NOT in labs!)
               
8. depression_risk = f(mood_state, anhedonia_flag, anxiety)
                  (NOT in labs!)
                  
9. severity_score = fatigue_functional_impairment [CRITICAL]
                 (NOT in labs!)
                 
10. disability_impact = daily_disability_percent [0-100]
                     (NOT in labs!)
                     
11. functional_impairment_severity = derived from Q5.4 + Q5.5
                                   (determines urgency)
```

---

## 7. HYBRID SCORING LOGIC (Week 1+)

### Path-Dependent Scoring:

**PATH A: No Labs (NHANES Rule-Based)**
```
Features: symptom-derived only
          ↓
Score: rule-based decision tree on 15 engineered features
       ↓
Output: top 3 fatigue drivers + testing recommendations
```

**PATH B: Has Labs (Hybrid - Lab + Symptom)**
```
Lab Values:
├─ Ferritin → iron_deficiency_risk
├─ TSH/Free T4 → thyroid_risk
├─ B12/Folate → b12_risk
└─ Hemoglobin → anemia_severity

+

Symptom Features:
├─ sleep_disorder_score
├─ post_exertional_malaise_flag
├─ anxiety_risk
├─ depression_risk
└─ functional_impairment_severity

     ↓

Hybrid Score:
├─ Lab-confirmed pathologies (weighted high)
├─ Symptom-only pathologies (ME/CFS, depression, sleep)
└─ Functional impact (determines urgency)

     ↓

Output: top 3 fatigue drivers + immediate actionable plan
```

---

## 8. WEEK-BY-WEEK IMPLEMENTATION

### WEEK 1 MVP: Hybrid Path + Lab Upload UI

**Deliverables**:
- ✅ Q0.0 & Q0.1 implemented (no OCR yet, manual entry fallback)
- ✅ Routing logic: hybrid path questions shown/hidden correctly
- ✅ Feature extraction: both paths work
- ✅ Hybrid scoring algorithm (lab + symptom combination)
- ✅ Results page: shows which drivers are lab-confirmed vs. symptom-derived
- ✅ Doctor PDF v1: integrates lab results + symptom patterns

**Key Code Path**:
```javascript
if (answers.q0_0 === 'lab_yes' && extractedLabs) {
  // HYBRID PATH
  const questionsToShow = getQuestionsForHybridPath(); // Q1, Q4, Q5
  const features = extractFeaturesHybrid(answers, extractedLabs);
  const drivers = scoreHybrid(features, extractedLabs);
} else {
  // FULL PATH
  const features = extractFeaturesFull(answers);
  const drivers = scoreNHANES(features);
}
```

### WEEK 2: OCR Integration + LLM Explanations

**Deliverables**:
- ✅ Tesseract.js OCR for lab parsing
- ✅ Auto-extraction of ferritin, TSH, B12, hemoglobin
- ✅ LLM explanations: "Your ferritin is 18 (low) which causes..."
- ✅ RAG with medical pathology knowledge
- ✅ PDF v2 with lab interpretations

### WEEK 3: Safety & Evaluation

**Deliverables**:
- ✅ Hallucination guardrails for lab interpretations
- ✅ Eval set of 20 scenarios (lab + symptom combinations)
- ✅ A/B testing framework for prompt variants

---

## 9. COMMON SCENARIOS & HANDLING

### Scenario 1: Normal Labs + Depression
```
User uploads labs:
├─ Ferritin: 45 (NORMAL)
├─ TSH: 2.1 (NORMAL)
└─ B12: 350 (NORMAL)

Answer mental health Q's:
├─ Q5.2: Mood = "Depressed"
├─ Q5.1: Anxiety = "Often"
└─ Q5.4: Impact = "Severe"

Result: "All labs normal, but depression driving fatigue"
Action: Mental health referral (not additional testing)
```

### Scenario 2: Low Ferritin + Post-Exertional Malaise
```
User uploads labs:
├─ Ferritin: 18 (LOW)
└─ TSH: 2.5 (NORMAL)

Answer activity Q's:
├─ Q4.3: PEM = "Yes"
└─ Q4.4: Onset = "Next day"

Result: Multi-factorial fatigue
├─ Iron deficiency (from labs)
├─ Possible ME/CFS (from PEM pattern)
└─ Action: Iron + activity pacing + specialist referral
```

### Scenario 3: No Labs, Sleep Disorder
```
User answers full assessment:
├─ Q1.2: Sleep quality = 2/10
├─ Q1.3: Wake-ups = "Very Often"
├─ Q1.4: Sleep issues = "Sleep paralysis"
└─ Q1.5: Duration = ">6 months"

Result: Sleep disorder pathway
Recommended tests: Sleep study, EEG, rule out sleep apnea
```

---

## 10. INTERVIEW TALKING POINTS

**"Why is your hybrid path better than just using labs?"**

> "Because fatigue has many etiologies, and not all of them show up in standard blood work. 
>
> **Lab-visible causes**: Iron deficiency, hypothyroidism, B12 deficiency
> 
> **Lab-invisible causes**: Post-exertional malaise (ME/CFS), sleep disorders, depression, anxiety
>
> So even if a user brings normal labs, we still ask about sleep quality, activity patterns, and mood. This catches multi-factorial cases.
>
> **Example**: A user with completely normal labs but ME/CFS would get missed if we only looked at labs. By asking about post-exertional malaise, we catch it."

**"How do you avoid making users redo assessments?"**

> "If they have labs, we skip the redundant questions. Nutrition module takes 2 minutes to assess via questions, but you get the same data from ferritin + B12 labs in seconds. Why waste the user's time?
>
> But we keep the critical questions that labs don't answer: sleep quality, PEM, depression, anxiety. Those need symptom data."

**"What if a user's lab results are incomplete?"**

> "We handle that gracefully. If they upload a lab with ferritin but no TSH, we skip the nutrition questions but ask all the hormonal questions (since we don't have TSH data). Features are marked as NULL where data is missing, and confidence scoring reflects the incompleteness."

---

## 11. FILES NEEDED FOR IMPLEMENTATION

**JSON Files** (in `/public`):
1. `assessment_tree.json` - Complete quiz structure (Q0.0-Q5.5)
2. `lab_normal_ranges.json` - Reference ranges for all biomarkers
3. `scoring_rules.json` - Both NHANES and hybrid scoring

**Python Modules** (in `/lib`):
1. `feature_extraction.py` - Raw → engineered features
2. `lab_ocr.py` - OCR extraction + validation (Week 2)
3. `scoring.py` - Both scoring algorithms
4. `hybrid_scorer.py` - Lab + symptom combination

---

## SUMMARY

The hybrid assessment path is a **strategic innovation**:
- ✅ Respects user time (skip redundant questions if labs available)
- ✅ Captures non-lab pathologies (ME/CFS, depression, sleep)
- ✅ Enables smarter diagnosis (lab + symptom combination)
- ✅ Remains transparent and traceable (every feature → every question → every score)

**Document Version**: 1.1 (Hybrid Lab Path)
**Last Updated**: March 9, 2026
**Status**: Ready for Week 1 implementation
