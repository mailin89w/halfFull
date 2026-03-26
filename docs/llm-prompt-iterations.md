# LLM Prompt Iteration Log

Each version covers both the MedGemma grounding prompt (Call 1) and the Groq synthesis prompt (Call 2), plus the all-clear path.

---

## V1–V5 (pre-log)

Early iterations. Single-call architecture (one Groq/MedGemma call). Not preserved.

---

## V6 — Two-call architecture

**Date:** 2026-03-25
**File:** `frontend/src/lib/prompts.ts` — `buildMedGemmaGroundingPromptV6`, `buildGroqSynthesisPromptV6`
**Architecture change:** Split into two calls:
- **Call 1 (MedGemma):** Clinical grounding — produces structured JSON with `supportedSuspicions`, `declinedSuspicions`, `recommendedSpecialties`. No prose.
- **Call 2 (Groq `llama-3.3-70b-versatile`):** Narrative synthesis — takes the grounding JSON and produces all patient-facing prose fields.

**Key design decisions:**
- MedGemma handles clinical verification; Groq handles communication quality
- `SECTION ROLE ASSIGNMENT` block enforces no cross-section repetition
- Risk calibration snapshot injected into both prompts
- `oneShot` example selection based on supported suspicion count
- All-clear path skips MedGemma entirely, calls Groq with `buildAllClearPrompt`

**Issues observed:**
- `personalizedSummary` came out generic and clinical: "You may be experiencing severe fatigue and potential thyroid abnormalities..."
- No connection between symptoms (fatigue treated as standalone, not linked to heavy periods / night sweats / sleep)
- `summaryPoints` hard-required 3–6 items → schema validation failures → 503
- `recoveryOutlook` hard-required → failures when Groq omitted it
- `declinedSuspicions` hard-failed on invalid diagnosisId in synthesis validator

---

## V7 — Conversational personalizedSummary + KNN block + fatigue-severity tone

**Date:** 2026-03-27
**File:** `frontend/src/lib/prompts.ts` — `buildGroqSynthesisPromptV7`, updated `buildAllClearPrompt`
**Route:** `frontend/app/api/deep-analyze/route.ts` — switched to `buildGroqSynthesisPromptV7`
**UI:** `frontend/app/results/page.tsx` — new KNN block "For people similar to you, it's worth checking"

### Changes vs V6

**1. personalizedSummary rewrite**

Old instruction:
> "1-2 sentence prose version of the above bullets, plus a screening-tool disclaimer."

New instruction:
> Name the actual symptoms from `keySymptoms`. Connect fatigue to other symptoms by name ("the heavy periods you mentioned", "your disrupted sleep schedule", "night sweats"). Warm second person. No disclaimer in this field. End with: "Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit."

**2. Fatigue-severity-aware opening**
- `fatigueSeverity === 3`: *"You're dealing with persistent, significant fatigue — and from what you shared, this isn't a standalone symptom..."*
- `fatigueSeverity === 0`: *"You mentioned some tiredness on certain days — and from what else you shared, there are a few patterns worth looking into together."*
- `fatigueSeverity === 1–2`: *"From what you shared, your fatigue is not a standalone symptom..."*

**3. All-clear personalizedSummary**

Updated to reference specific patterns from the patient's answers rather than generic "your answers look reassuring." Example: *"From what you shared, the tiredness you experience seems connected to [specific pattern] rather than pointing to an underlying condition."*

**4. Bayesian gain signals passed to synthesis**

`route.ts` computes `topBayesianConditions` — conditions where Bayesian follow-up questions yielded the most confirming answers. Passed to V7 prompt so Groq knows which conditions had the strongest Bayesian support.

```
topBayesianConditions: ["iron (3 confirming signals)", "thyroid (2 confirming signals)"]
```

**5. Schema validation relaxed (in `lib/medgemma-safety.ts`)**
- `summaryPoints`: no longer required (was 3–6 mandatory)
- `recoveryOutlook`: now optional
- `declinedSuspicions` invalid ids: `continue` instead of `return err`

**6. KNN block in UI**

New section at the bottom of results (only shown when live MedGemma ran and `knnSignals` present):

> **For people similar to you, it's worth checking**
> In 50 people from our database with a similar fatigue pattern, these lab markers were more commonly abnormal.
> `[HIGH] Ferritin — 74% of similar people · 2.3× more common`
> `[LOW] TSH — 61% of similar people`

---

## Notes for V8

- Consider extracting key symptom names from `answeredQuestionsText` before the prompt (pre-processing) rather than relying on Groq to pull them from nested `keySymptoms` arrays
- Consider adding a `personalizedSummaryDraft` field to the grounding result so MedGemma pre-writes the symptom connections in V8
- The `nextSteps` 2-sentence limit sometimes feels too short for cases with 3 specialists — consider expanding to 3–4 sentences in complex cases
