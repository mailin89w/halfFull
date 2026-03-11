# HalfFull Assessment Quiz Tree
## Complete Implementation Package (v1.1 - Hybrid Lab Path)

---

## 📋 CONTENTS OF THIS UPDATED PACKAGE

This package contains everything you need to implement the intelligent hybrid assessment in HalfFull:

### 1. **HalfFull_Assessment_Quiz_Tree.xlsx** 
   - **Purpose**: Visual reference of all 24 questions (now with Q0.0 & Q0.1 lab gate)
   - **Updated Features**:
     - Module 0 (Pre-Assessment): Q0.0 Lab Gate + Q0.1 Lab Upload
     - Modules 1-5: Core assessment (24 total questions)
     - Hybrid path indicators (which modules shown for each path)
   - **Use**: Print/view for complete overview, share with stakeholders

### 2. **Assessment_Quiz_Tree_Documentation_v1.1.md**
   - **Purpose**: Complete design documentation with hybrid lab path
   - **Contains**:
     - Three assessment paths explained (full vs. hybrid)
     - Module 0 (Pre-Assessment) detailed spec
     - All 5 core modules with conditional logic
     - Feature engineering pipeline
     - Week-by-week implementation roadmap
     - Interview talking points (updated for hybrid)
   - **Key Addition**: "Why This Design?" section explaining why we don't skip mental health/activity modules even with labs

### 3. **Assessment_Tree_Schema_v1.1.json**
   - **Purpose**: JSON Schema validating the complete structure
   - **Updates**:
     - `q0.0` and `q0.1` specification
     - Lab biomarkers section
     - `shown_in_paths` field for each module
     - `path_determination` routing logic
     - Lab extraction patterns for OCR
   - **Use**: Validate quiz_tree.json in CI/CD

### 4. **Assessment_Tree_Complete_Example_v1.1.json**
   - **Purpose**: Production-ready JSON with all 24 questions + hybrid routing
   - **Updates**:
     - Q0.0: "Do you have recent lab results?"
     - Q0.1: Lab upload with OCR extraction fields
     - All questions tagged with `shown_in_paths`: ["full"] or ["hybrid"] or ["full", "hybrid"]
     - Routing logic shows which questions to skip for hybrid path
   - **Use**: Copy directly into `/public/assessment_tree.json` in your Next.js app

### 5. **README_Assessment_Quiz_Tree_v1.1.md** (this file)
   - **Purpose**: Quick start guide with hybrid path examples
   - **Updated**: Shows hybrid path implementation code

---

## 🚀 QUICK START: WEEK 1 MVP (Hybrid Path Enabled)

### Step 1: Copy the JSON
```bash
cp Assessment_Tree_Complete_Example_v1.1.json /your-nextjs-app/public/assessment_tree.json
```

### Step 2: Load in Next.js
```typescript
// lib/assessment.ts
import assessmentTree from '@/public/assessment_tree.json';

export function getModule(moduleId: string) {
  return assessmentTree.assessment.modules.find(m => m.id === moduleId);
}

export function getQuestion(moduleId: string, questionId: string) {
  const module = getModule(moduleId);
  return module?.questions.find(q => q.id === questionId);
}

// NEW: Get questions for hybrid path
export function getQuestionsToShow(hasLabs: boolean) {
  const allQuestions = assessmentTree.assessment.modules
    .flatMap(m => m.questions);
  
  if (!hasLabs) {
    // Full path: show all questions
    return allQuestions;
  }
  
  // Hybrid path: show only questions in both paths or hybrid path
  return allQuestions.filter(q => {
    const module = getModule(q.id.split('.')[0]);
    return module?.shown_in_paths.includes('hybrid');
  });
}
```

### Step 3: Build Lab Gate Component
```typescript
// components/LabGate.tsx
import { useState } from 'react';

interface LabGateProps {
  onPathDetermined: (hasLabs: boolean) => void;
}

export function LabGate({ onPathDetermined }: LabGateProps) {
  const [selected, setSelected] = useState<'yes' | 'no' | null>(null);

  const handleSelect = (value: 'yes' | 'no') => {
    setSelected(value);
    localStorage.setItem('has_recent_labs', value);
    onPathDetermined(value === 'yes');
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Do you have recent lab results?</h2>
        <p className="text-gray-600">
          If you've had blood work done in the last 6 months, you can upload it now. 
          This will speed up your assessment and give us more precise results.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => handleSelect('yes')}
          className={`p-6 border-2 rounded-lg transition ${
            selected === 'yes'
              ? 'border-blue-600 bg-blue-50'
              : 'border-gray-300 hover:border-blue-300'
          }`}
        >
          <div className="text-lg font-semibold">Yes</div>
          <div className="text-sm text-gray-600">I have recent labs</div>
        </button>

        <button
          onClick={() => handleSelect('no')}
          className={`p-6 border-2 rounded-lg transition ${
            selected === 'no'
              ? 'border-blue-600 bg-blue-50'
              : 'border-gray-300 hover:border-blue-300'
          }`}
        >
          <div className="text-lg font-semibold">No</div>
          <div className="text-sm text-gray-600">I don't have recent labs</div>
        </button>
      </div>
    </div>
  );
}
```

### Step 4: Lab Upload Component (Week 1: Manual Entry Fallback)
```typescript
// components/LabUpload.tsx
import { useState } from 'react';

interface LabUploadProps {
  onLabsSubmitted: (labs: Record<string, number>) => void;
}

export function LabUpload({ onLabsSubmitted }: LabUploadProps) {
  const [method, setMethod] = useState<'upload' | 'manual'>('manual');
  const [labs, setLabs] = useState<Record<string, number>>({});

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Week 1: Just store file path, no OCR yet
    // Week 2: Implement Tesseract.js OCR
    console.log('File uploaded:', file.name);
    // TODO: Implement OCR extraction
  };

  const handleManualEntry = (key: string, value: string) => {
    setLabs({
      ...labs,
      [key]: parseFloat(value) || 0
    });
  };

  const handleSubmit = () => {
    localStorage.setItem('uploaded_labs', JSON.stringify(labs));
    onLabsSubmitted(labs);
  };

  if (method === 'upload') {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-bold">Upload Lab Results</h3>
        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleFileUpload}
        />
        <button
          onClick={() => setMethod('manual')}
          className="text-blue-600 underline"
        >
          Can't upload? Enter manually →
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-bold">Enter Your Lab Values</h3>

      <div className="space-y-3">
        {['ferritin', 'tsh', 'hemoglobin', 'vitamin_b12'].map(lab => (
          <div key={lab}>
            <label className="block text-sm font-medium mb-1 capitalize">
              {lab.replace('_', ' ')} (ng/mL)
            </label>
            <input
              type="number"
              step="0.1"
              onChange={(e) => handleManualEntry(lab, e.target.value)}
              className="w-full border px-3 py-2 rounded"
              placeholder="Enter value"
            />
          </div>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        className="w-full bg-blue-600 text-white py-2 rounded font-medium"
      >
        Submit Labs
      </button>
    </div>
  );
}
```

### Step 5: Routing Logic (Path Determination)
```typescript
// lib/routing.ts

export function getNextQuestions(
  hasLabs: boolean,
  answers: Record<string, string>
): string[] {
  if (!hasLabs) {
    // FULL PATH: Show all 24 questions
    return [
      'q0.0', 'q0.1',  // Pre-assessment (only Q0.0)
      'q1.1', 'q1.2', 'q1.3', 'q1.4', 'q1.5',  // Sleep (always)
      'q2.1', 'q2.2', 'q2.3', 'q2.4', 'q2.5',  // Nutrition (only no labs)
      'q3.1', 'q3.2', 'q3.3', 'q3.4', 'q3.5', 'q3.6',  // Hormonal (only no labs)
      'q4.1', 'q4.2', 'q4.3', 'q4.4', 'q4.5',  // Activity (always)
      'q5.1', 'q5.2', 'q5.3', 'q5.4', 'q5.5'   // Mental (always)
    ];
  }

  // HYBRID PATH: Skip nutrition & hormonal, keep sleep/activity/mental
  return [
    'q0.0',  // Just Q0.0, skip Q0.1 after upload
    'q1.1', 'q1.2', 'q1.3', 'q1.4', 'q1.5',  // Sleep (always)
    // SKIP Q2.x (nutrition - have ferritin/B12)
    // SKIP Q3.x (hormonal - have TSH)
    'q4.1', 'q4.2', 'q4.3', 'q4.4', 'q4.5',  // Activity (always)
    'q5.1', 'q5.2', 'q5.3', 'q5.4', 'q5.5'   // Mental (always)
  ];
}
```

### Step 6: Feature Extraction (Both Paths)
```typescript
// lib/features.ts

export function extractFeatures(
  answers: Record<string, string>,
  labs?: Record<string, number>
) {
  const features = {
    // Always from assessment
    sleep_quality_score: parseInt(answers.q1_2) || 0,
    post_exertional_malaise: answers.q4_3 === 'pem_yes' ? 1 : 0,
    fatigue_functional_impairment: encodeOrdinal(answers.q5_4),
    anxiety_frequency: encodeOrdinal(answers.q5_1),
    mood_state: encodeOrdinal(answers.q5_2),
    
    // From labs (if available)
    ...(labs?.ferritin && {
      ferritin_level: labs.ferritin,
      iron_deficiency_from_labs: labs.ferritin < 30 ? 1 : 0
    }),
    ...(labs?.tsh && {
      tsh_level: labs.tsh,
      thyroid_dysfunction_from_labs: (labs.tsh > 4.5 || labs.tsh < 0.4) ? 1 : 0
    }),
    
    // From assessment (only if no labs)
    ...(!labs?.ferritin && {
      iron_deficiency_from_symptoms: calculateIronRisk(answers)
    }),
    ...(!labs?.tsh && {
      thyroid_risk_from_symptoms: calculateThyroidRisk(answers)
    })
  };

  return features;
}
```

### Step 7: Hybrid Scoring
```typescript
// lib/scoring.ts

export function scoreAssessment(
  features: Record<string, number>,
  labs?: Record<string, number>
): FatigueDriver[] {
  const drivers: FatigueDriver[] = [];

  // ===== LAB-BASED DRIVERS (if labs available) =====
  if (labs) {
    if (labs.ferritin < 30) {
      drivers.push({
        name: "Iron Deficiency Anemia",
        evidence: `Ferritin ${labs.ferritin} ng/mL (LOW, normal >30)`,
        severity: labs.ferritin < 15 ? "CRITICAL" : "HIGH",
        source: "lab",
        recommendation: "Iron supplementation, retest in 6-8 weeks"
      });
    }

    if (labs.tsh > 4.5 || labs.tsh < 0.4) {
      drivers.push({
        name: "Thyroid Dysfunction",
        evidence: `TSH ${labs.tsh} mIU/L (abnormal, normal 0.4-4.5)`,
        severity: "HIGH",
        source: "lab",
        recommendation: "See endocrinologist, may need levothyroxine"
      });
    }
  }

  // ===== SYMPTOM-BASED DRIVERS (ALWAYS) =====

  if (features.sleep_quality_score < 5) {
    drivers.push({
      name: "Sleep Disorder",
      evidence: `Sleep quality ${features.sleep_quality_score}/10`,
      severity: "HIGH",
      source: "symptom",
      recommendation: "Sleep study, rule out sleep apnea"
    });
  }

  if (features.post_exertional_malaise === 1) {
    drivers.push({
      name: "Possible ME/CFS",
      evidence: "Post-exertional malaise detected",
      severity: "HIGH",
      source: "symptom",
      recommendation: "Activity pacing, specialist referral"
    });
  }

  if (features.mood_state < 2 || features.anxiety_frequency > 3) {
    drivers.push({
      name: "Depression / Anxiety",
      evidence: `Mood score: ${features.mood_state}, Anxiety: ${features.anxiety_frequency}`,
      severity: "HIGH",
      source: "symptom",
      recommendation: "Mental health referral"
    });
  }

  // THE CRITICAL FEATURE
  drivers.push({
    name: "Functional Impact",
    evidence: `Severity: ${features.fatigue_functional_impairment}/3`,
    severity: features.fatigue_functional_impairment >= 2 ? "CRITICAL" : "MEDIUM",
    source: "symptom",
    recommendation: "Urgent medical evaluation if severe"
  });

  // Sort by severity
  return drivers.sort((a, b) => {
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return (order[a.severity] ?? 4) - (order[b.severity] ?? 4);
  });
}
```

---

## 📊 DATA FLOW: WITH HYBRID PATH

```
START
│
├─ Q0.0: "Do you have recent labs?"
│  │
│  ├─ YES → Q0.1: Lab Upload
│  │  │
│  │  ├─ Extract: ferritin, TSH, B12, hemoglobin
│  │  │
│  │  └─ HYBRID PATH (10-12 questions):
│  │     ├─ Q1.1-Q1.5 (Sleep - labs don't measure)
│  │     ├─ [SKIP Q2.1-Q2.5 - have ferritin/B12]
│  │     ├─ [SKIP Q3.1-Q3.6 - have TSH]
│  │     ├─ Q4.1-Q4.5 (Activity - PEM not in labs)
│  │     ├─ Q5.1-Q5.5 (Mental - depression not in labs)
│  │     └─ → HYBRID SCORING (lab values + symptom features)
│  │
│  └─ NO → FULL PATH (24 questions):
│     ├─ Q1.1-Q1.5 (Sleep)
│     ├─ Q2.1-Q2.5 (Nutrition)
│     ├─ Q3.1-Q3.6 (Hormonal)
│     ├─ Q4.1-Q4.5 (Activity)
│     ├─ Q5.1-Q5.5 (Mental)
│     └─ → NHANES RULE-BASED SCORING
│
└─ RESULTS: Top 3 fatigue drivers ranked
```

---

## ✅ KEY DIFFERENCES: HYBRID PATH

### What Gets Skipped (Why?)
| Questions | Why Skipped | Data Source Instead |
|-----------|---|---|
| Q2.1-Q2.5 (Nutrition) | We have ferritin, B12, folate from labs | Lab values are more precise |
| Q3.1-Q3.6 (Hormonal) | We have TSH, Free T4 from labs | Lab values are definitive |

### What ALWAYS Gets Asked (Why?)
| Questions | Why Essential | Lab Alternative |
|-----------|---|---|
| Q1.1-Q1.5 (Sleep) | Sleep disorders NOT measured in blood | No lab marker exists |
| Q4.1-Q4.5 (Activity) | Post-exertional malaise NOT in labs | Symptom-based diagnosis only |
| Q5.1-Q5.5 (Mental) | Depression/anxiety NOT in standard labs | Symptom-based diagnosis only |

**Example**: User has normal ferritin (45 ng/mL), normal TSH (2.5 mIU/L), but answers "Yes" to Q5.2 (depressed mood) and Q4.3 (post-exertional malaise).

**Result**: "Normal labs + Depression + PEM" → Diagnose depression + possible ME/CFS, not just "everything normal"

---

## 🎯 INTERVIEW TALKING POINT

> **Interviewer**: "Your hybrid path skips some questions if labs are available. Doesn't that lose information?"
>
> **You**: "No, it's smarter than that. We skip redundant information - if you have a ferritin value, asking about iron food frequency and dietary restrictions is noise.
>
> But we ALWAYS ask about:
> - Sleep quality (not in blood work)
> - Post-exertional malaise (hallmark of ME/CFS, not in blood work)
> - Mental health (depression/anxiety not in labs)
>
> So a user with completely normal labs but ME/CFS still gets diagnosed because we ask Q4.3. A user with normal labs + depression gets diagnosed because we ask Q5.2-5.3.
>
> This is actually MORE robust than just reading labs, because we capture multi-factorial causes."

---

## 📝 WEEK 1 IMPLEMENTATION CHECKLIST

- [ ] Q0.0 & Q0.1 components built
- [ ] Lab gate routing logic working
- [ ] Hybrid path questions shown/hidden correctly
- [ ] Manual lab entry fields (no OCR yet)
- [ ] Feature extraction for both paths
- [ ] Hybrid scoring algorithm
- [ ] Results page shows source (lab vs. symptom)
- [ ] Doctor PDF v1 integrates lab values
- [ ] localStorage persistence working
- [ ] All paths tested (full, hybrid with labs, hybrid with manual entry)

---

## 🚀 WEEK 2: OCR INTEGRATION

Add to lab upload:
```typescript
// Week 2: Add OCR
import Tesseract from 'tesseract.js';

async function extractLabValuesOCR(file: File) {
  const { data: { text } } = await Tesseract.recognize(file, 'eng');
  
  const labs = {};
  const patterns = {
    ferritin: /ferritin[:\s]+(\d+\.?\d*)/i,
    tsh: /tsh[:\s]+(\d+\.?\d*)/i,
    // ... more patterns
  };
  
  for (const [key, pattern] of Object.entries(patterns)) {
    const match = text.match(pattern);
    if (match) {
      labs[key] = parseFloat(match[1]);
    }
  }
  
  return labs;
}
```

---

## FILES YOU HAVE

1. ✅ **Assessment_Quiz_Tree_Documentation_v1.1.md** - Read this first
2. ✅ **Assessment_Tree_Schema_v1.1.json** - For CI/CD validation
3. ✅ **Assessment_Tree_Complete_Example_v1.1.json** - Copy to `/public`
4. ✅ **README_Assessment_Quiz_Tree_v1.1.md** - This file

---

## SUMMARY

The hybrid assessment is **strategically smart**:
- ✅ Respects user time (skip redundant questions if labs available)
- ✅ Avoids false negatives (always ask about non-lab pathologies)
- ✅ Enables hybrid diagnosis (lab + symptom combination)
- ✅ Remains transparent (every feature → every score)

**Version**: 1.1 (Hybrid Lab Path)
**Last Updated**: March 9, 2026
**Status**: Ready for Week 1 implementation
