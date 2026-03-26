# MedGemma Prompt Changelog

This file keeps the MedGemma prompt history explicit. The current prompt is `V6`. Prior versions are preserved below.

## Current live prompt set

- Shared prompt module: `frontend/src/lib/prompts.ts`
- JSON-only system prompt: `MEDGEMMA_JSON_SYSTEM_V1`
- **V6 Call 1 (MedGemma grounding):** `buildMedGemmaGroundingPromptV6(...)`
- **V6 Call 2 (Groq synthesis):** `buildGroqSynthesisPromptV6(...)`
- All-clear path (Groq): `buildAllClearPrompt(...)` passed to `synthesizeNarrativeWithGroqV6`
- Lightweight analysis prompt: `buildAnalyzePrompt(...)`
- V6 Groq synthesis function: `synthesizeNarrativeWithGroqV6` in `deepAnalyzeSafety.ts`
- V6 grounding validation: `validateMedGemmaGroundingSchema` in `medgemma-safety.ts`

## Version table

| Version | Date | Status | Scope | What changed | Why it changed | Evidence / note |
| --- | --- | --- | --- | --- | --- | --- |
| V6 | 2026-03-25 | Current working version | `deep-analyze` | Split into two calls: MedGemma clinical grounding (Call 1) + Groq narrative synthesis (Call 2). PDF labs removed from MedGemma. Tone/narrative moved entirely to Groq. Full MedGemma output logged to Supabase. New `declinedSuspicions` field. `confidence` field on insights. Strong doctor kit with pre-visit structure (`bringToAppointment`, `whatToSay`). 3-step decision tree with binary gates. Anti-generic discussionPoints rule with negative example. Minimum 1 doctor if insights non-empty. `llama-3.3-70b-versatile` as primary synthesis model. One-shot example slot (pending user approval of examples). | Research: general-purpose models are 25 points better at hallucination-free narrative (medRxiv 2025). MedGemma should do narrow clinical grounding only; prose generation belongs in Groq. PDF labs removed from MedGemma call because structured Q&A is sufficient for grounding and PDF parsing is unreliable. | Architecture implemented. Examples pending review. |
| V5 | 2026-03-25 | Previous version | `deep-analyze` | Richer input context; explicit verify/decline step for filtered disease suspicions; no clarification-question framing; healthy/no-suspect path; doctor-specific kits; integrated safety-tone rewrite in the MedGemma flow. | Give MedGemma the full case context, make the fatigue summary more useful and personalized, and produce doctor guidance that is more case-specific and specialist-aware. | Superseded by V6. Prompt templates preserved below. |
| V4 | 2026-03-25 | Previous live structure | `analyze` + `deep-analyze` | Prompts extracted into `frontend/src/lib/prompts.ts`; wording tightened to emphasize grounding, allowed conditions, lower-certainty framing, and test recommendations tied to flagged evidence only. | Make prompt iteration easier, reduce hallucinated conditions/tests, and keep a single source of truth. | No eval run recorded yet. Change was based on prompt hygiene and maintainability. |
| V3 | 2026-03-25 | Historical | `deep-analyze` | Added optional KNN neighbour-lab evidence block to the prompt; retained all-clear path and doctor-kit output shape. | Improve specificity of test suggestions using similar-patient lab patterns. | Code change is visible in git history. No prompt-specific eval notes found in repo docs. |
| V2 | 2026-03-25 | Historical | `deep-analyze` | Added all-clear prompt variant, clarification-answer grounding, stronger safety phrasing, and the expanded JSON response with doctor-kit fields. | Better UX for healthy users, more personalized outputs, and safer language for possible conditions. | Code change is visible in git history. No separate evaluation artifact found yet. |
| V1 | Earlier MVP | Historical | `analyze` / early `deep-analyze` | Single hardcoded prompt focused on JSON output with summary, insights, and next steps. | Fast MVP path to generate interpretable outputs from top ML conditions. | Earliest version found in route history; no changelog existed before this file. |

## Restored V1-V4 table

This is the earlier changelog table restored in its old style so the previous progression is preserved exactly as a standalone reference.

| Version | Date | Where introduced | Scope | What changed | Why it changed | Evidence / note |
| --- | --- | --- | --- | --- | --- | --- |
| V4 | 2026-03-25 | working tree | `analyze` + `deep-analyze` | Prompts extracted into `frontend/src/lib/prompts.ts`; wording tightened to emphasize grounding, allowed conditions, lower-certainty framing, and test recommendations tied to flagged evidence only. | Make prompt iteration easier, reduce hallucinated conditions/tests, and keep a single source of truth. | No eval run recorded yet. Change is based on prompt hygiene and maintainability. |
| V3 | 2026-03-25 | `f8756f7`, `f90a7f2` | `deep-analyze` | Added optional KNN neighbour-lab evidence block to the prompt; retained all-clear path and doctor-kit output shape. | Improve specificity of test suggestions using similar-patient lab patterns. | Code change is visible in git history. No prompt-specific eval notes found in repo docs. |
| V2 | 2026-03-25 | `a9160fb`, `7f3bb2e` | `deep-analyze` | Added all-clear prompt variant, clarification-answer grounding, stronger safety phrasing, and the expanded JSON response with doctor-kit fields. | Better UX for healthy users, more personalized outputs, and safer language for possible conditions. | Code change is visible in git history. No separate evaluation artifact found yet. |
| V1 | Earlier MVP | legacy route history | `analyze` / early `deep-analyze` | Single hardcoded prompt focused on JSON output with summary, insights, and next steps. | Fast MVP path to generate interpretable outputs from top ML conditions. | Earliest version found in route history; no changelog existed before this file. |

## Current system prompt

```text
You output valid JSON only. No markdown, no thinking, no explanations, no preamble. Start your response immediately with { and end with }.
```

## V5 deep-analysis prompt template

Source: `buildDeepAnalyzePrompt(...)` in `frontend/src/lib/prompts.ts`

```text
You are MedGemma acting as a medical screening synthesis assistant for a fatigue assessment product.

Your job is NOT to ask clarification questions. The Bayesian layer already handled follow-up questioning. Your job is to review all provided evidence, verify which disease suspicions are still supported, decline the ones that are not supported, and produce a useful doctor-ready summary.

We tested 11 diseases as fatigue-related signals in our filtering layer:
${evaluatedDiseases}

${candidateInstruction}

${detailInstruction}

Use the full evidence below:

PATIENT SUMMARY BLOCK:
${symptomsText}

HIGH-SCORING FILTERED DISEASES:
${flaggedAreasText}

ALREADY CONFIRMED CONDITIONS:
${confirmedText}

BAYESIAN EVIDENCE (already collected upstream, not new clarification requests):
${bayesianEvidenceText}

QUESTION + ANSWER DICTIONARY (question text, feature name, answer label, raw answer):
${answeredQuestionsText}

RAW STRUCTURED ANSWERS JSON:
${structuredAnswersJson}

UPLOADED LABS (raw extracted text plus structured values before normalization):
${uploadedLabsText}
${knnLabText ? `\n\nNEAREST-NEIGHBOUR LAB SIGNALS:\n${knnLabText}` : ''}

MODEL SCORE SUMMARY:
${scoreSummaryJson}

Reasoning task:
1. Identify the fatigue drivers and symptom clusters that matter most clinically for this specific patient.
2. Review the filtered disease hypotheses against the user evidence, raw labs, and Bayesian evidence.
3. Keep only the disease suspicions that are still supported after review. Decline unsupported hypotheses.
4. It is allowed that no disease suspects remain supported. In that case return an all-clear style result.
5. Recommend up to 3 clinicians only when they are genuinely relevant to the supported disease risks or known confirmed conditions.
6. Build doctor-specific kits that separate symptoms to discuss, tests worth considering, and high-value discussion points.

Respond with valid JSON only. No markdown, no preamble:
{
  "personalizedSummary": "Maximum 10 sentences. This is one combined section that makes the patient feel heard. Summarise the most important fatigue-related symptoms, the strongest possible drivers, and any already confirmed conditions that matter for interpretation. Help the patient understand which symptoms are most worth discussing with a doctor. Include a brief disclaimer that this is a screening tool, not a diagnosis.",
  "insights": [
    {
      "diagnosisId": "exact id from: iron|thyroid|sleep|vitamins|stress|postviral|anemia|iron_deficiency|kidney|sleep_disorder|liver|prediabetes|inflammation|electrolytes|hepatitis|perimenopause",
      "personalNote": "1-3 sentences explaining why this supported suspicion still fits this patient's specific symptoms, lab data, and Bayesian evidence."
    }
  ],
  "nextSteps": "Up to 6 sentences. Title in the UI will be 'Next steps - talk to a doctor'. Explain which doctors are worth seeing first and why, tied to this case rather than generic advice.",
  "doctorKitSummary": "1-2 first-person sentences the patient can use to open a doctor visit.",
  "doctorKitQuestions": [
    "Legacy compatibility field. Reuse the strongest discussion points if needed."
  ],
  "doctorKitArguments": [
    "Legacy compatibility field. Reuse the strongest evidence-based discussion points if needed."
  ],
  "recommendedDoctors": [
    {
      "specialty": "GP | Endocrinologist | Sleep specialist | Nephrologist | Hepatologist | Gynaecologist | other relevant doctor",
      "priority": "start_here | consider_next | specialist_if_needed",
      "reason": "1-3 sentences explaining why this doctor is relevant for this exact case and which symptom patterns or known conditions to discuss with them.",
      "symptomsToDiscuss": [
        "Concrete symptom or pattern from the assessment"
      ],
      "suggestedTests": [
        "Specific test or referral relevant to this doctor"
      ]
    }
  ],
  "doctorKits": [
    {
      "specialty": "same specialty as above",
      "openingSummary": "1-2 first-person sentences tailored to this specialist.",
      "concerningSymptoms": [
        "Symptoms or patterns relevant to this doctor only"
      ],
      "recommendedTests": [
        "Tests or referrals relevant to this doctor only"
      ],
      "discussionPoints": [
        "High-value evidence-based question or argument that goes beyond generic common-sense phrasing",
        "Another targeted question or argument"
      ]
    }
  ],
  "allClear": false
}
```

## V6 prompt templates

### V6 Call 1 — MedGemma grounding prompt

Source: `buildMedGemmaGroundingPromptV6(...)` in `frontend/src/lib/prompts.ts`

Key design decisions vs V5:
- PDF labs **removed** — only structured Q&A, Bayesian evidence, and ML scores
- "Follow the evidence, not your priors" instruction added (addresses MedGemma over-applying common-disease priors)
- 3-step decision tree with explicit binary gates (replaces 6-step verb list)
- `declinedSuspicions` is a required field — model cannot silently omit unsupported hypotheses
- `confidence` (probable / possible / worth_ruling_out) added to every supportedSuspicion
- `anchorEvidence` must name a specific feature/question from the record — no generic statements
- No narrative prose at all — MedGemma's only job is classification + one anchor fact per decision
- `max_tokens: 800`, `temperature: 0.1` — narrow and deterministic

Full template: see `buildMedGemmaGroundingPromptV6` in `frontend/src/lib/prompts.ts`

### V6 Call 2 — Groq synthesis prompt

Source: `buildGroqSynthesisPromptV6(...)` in `frontend/src/lib/prompts.ts`
Model: `llama-3.3-70b-versatile`, timeout 30s, max_tokens 3500, temperature 0.3

Key design decisions vs V5:
- **Grounding rule added back** (dropped from V5): "Every sentence must reference THIS patient's data. Do not use generic filler."
- Anti-generic `discussionPoints` rule with negative example: "DO NOT write 'Ask your doctor if you should get blood tests.' DO write things like: 'My questionnaire flagged heavy periods with clotting lasting 8 days — I want to ask specifically whether serum ferritin plus transferrin saturation is warranted before any supplementation decision.'"
- **Minimum doctor rule**: "If insights is non-empty, you MUST include at least 1 recommendedDoctor. Returning 0 doctors when there are active suspicions is a product error."
- Strong doctor kit: `bringToAppointment` list + `whatToSay` opening statement + `keySymptoms` per specialist
- `openingSummary` expanded to 2-3 sentences (was 1-2)
- `doctorKitSummary` expanded to 2-3 sentences naming duration and specific symptoms
- insights only from `supportedSuspicions` (explicit rule — no additions from Groq's own reasoning)
- `oneShot` parameter slot for approved example (currently `null` — pending review)

Full template: see `buildGroqSynthesisPromptV6` in `frontend/src/lib/prompts.ts`

### V6 architecture changes

```
Before V6 (V5):
  MedGemma → full deep-analyze (clinical + narrative + doctor kit + safety)
  Groq → light safety rewrite (5s timeout, 1000 tokens, patch only)

After V6:
  MedGemma (Call 1) → grounding only: supportedSuspicions, declinedSuspicions, medicationFlags
                       (no PDF labs, no prose, 800 tokens, 0.1 temp)
  Groq (Call 2)     → full synthesis: all narrative fields + strong doctor kit
                       (llama-3.3-70b-versatile, 30s timeout, 3500 tokens)
  Supabase log      → medgemma_grounding_raw (full raw output before any processing)
  Supabase log      → deep_analyze (final result with groundingResult included)
```

## V5 deep-analysis prompt template

Source: `buildDeepAnalyzePrompt(...)` — preserved for reference, superseded by V6.

```text
You are MedGemma acting as a medical screening synthesis assistant for a fatigue assessment product.

Your job is NOT to ask clarification questions. The Bayesian layer already handled follow-up questioning. Your job is to review all provided evidence, verify which disease suspicions are still supported, decline the ones that are not supported, and produce a useful doctor-ready summary.

We tested 11 diseases as fatigue-related signals in our filtering layer:
${evaluatedDiseases}

${candidateInstruction}

${detailInstruction}

Use the full evidence below:

PATIENT SUMMARY BLOCK:
${symptomsText}

HIGH-SCORING FILTERED DISEASES:
${flaggedAreasText}

ALREADY CONFIRMED CONDITIONS:
${confirmedText}

BAYESIAN EVIDENCE (already collected upstream, not new clarification requests):
${bayesianEvidenceText}

QUESTION + ANSWER DICTIONARY (question text, feature name, answer label, raw answer):
${answeredQuestionsText}

RAW STRUCTURED ANSWERS JSON:
${structuredAnswersJson}

UPLOADED LABS (raw extracted text plus structured values before normalization):
${uploadedLabsText}
[NEAREST-NEIGHBOUR LAB SIGNALS if available]

MODEL SCORE SUMMARY:
${scoreSummaryJson}

Reasoning task:
1. Identify the fatigue drivers and symptom clusters that matter most clinically for this specific patient.
2. Review the filtered disease hypotheses against the user evidence, raw labs, and Bayesian evidence.
3. Keep only the disease suspicions that are still supported after review. Decline unsupported hypotheses.
4. It is allowed that no disease suspects remain supported. In that case return an all-clear style result.
5. Recommend up to 3 clinicians only when they are genuinely relevant to the supported disease risks or known confirmed conditions.
6. Build doctor-specific kits that separate symptoms to discuss, tests worth considering, and high-value discussion points.

[JSON schema — see V5 section below for full schema]
```

## V4 deep-analysis prompt template

Preserved from the previous shared prompt structure.

```text
You are a medical AI generating a personalised fatigue report. Reference the patient's actual symptoms and follow-up answers. Never give generic advice.

PATIENT DATA:
${symptomsText}

TOP-3 FLAGGED CONDITIONS (posterior probabilities after Bayesian update):
${flaggedAreasText}
${clarificationText ? `\nCLARIFICATION ANSWERS (patient answered these follow-up questions - treat as confirmed findings):\n${clarificationText}` : ''}${knnLabText ? `\n\n${knnLabText}` : ''}

Before generating the JSON, reason through these steps internally:
1. What is the patient's most prominent symptom burden?
2. Which flagged condition best explains it and why?
3. Which tests are most directly useful to confirm or rule out the leading possibilities?
Then generate the JSON based on your reasoning. Do not include the reasoning in the output.

Respond with valid JSON only. No markdown, no preamble:
{
  "personalizedSummary": "2 sentences. Name the leading possible driver, connect it directly to what this patient reported, and include a brief disclaimer that this is a screening tool.",
  "insights": [
    {"diagnosisId": "exact id from: iron|thyroid|sleep|vitamins|stress|postviral|anemia|iron_deficiency|kidney|sleep_disorder|liver|prediabetes|inflammation|electrolytes|hepatitis|perimenopause", "personalNote": "1-2 sentences explaining why THIS flagged area fits this patient's specific reported symptoms."}
  ],
  "nextSteps": "2 sentences. Tell the patient which tests are most worth asking for next and why, based on their specific profile.",
  "doctorKitSummary": "2 sentences in first person that the patient can read aloud to open their GP appointment. It must mention their top symptom, how it affects daily life, and what they want to rule out.",
  "doctorKitQuestions": [
    "Specific assertive question for the GP tied to this patient's top flagged area",
    "Specific question about a second flagged area or the next diagnostic step"
  ],
  "doctorKitArguments": [
    "Argument referencing this patient's specific symptoms to justify requesting test 1",
    "Argument referencing this patient's specific symptoms to justify requesting test 2"
  ]
}

Rules:
- insights: one entry per flagged area, max 4 total. Prioritise ML-flagged conditions: ${prioritizedConditions.join(', ') || 'none'}.
- doctorKitQuestions: exactly 2 items.
- doctorKitArguments: exactly 2 items.
- Every string must reference THIS patient's data. Do not use generic filler.
- Only discuss flagged conditions or the supplied neighbour-lab signals. Do not invent extra conditions.
- If one flagged area is weaker, describe it as lower-priority rather than speaking with certainty.
- Recommend tests that are directly connected to the flagged conditions or supplied lab-signal evidence.
- Complete the full JSON without truncating.
- You are a screening tool, not a doctor. Never state or imply a diagnosis.
- Always frame findings as "may suggest", "could indicate", or "worth discussing with your GP".
- Never use alarming language. Never tell the patient they are seriously ill.
```

## V3 note

V3 used the same general prompt family as V4 but was the version where the KNN neighbour-lab evidence block was first added to the MedGemma context. The surrounding output shape remained broadly the same.

## V2 note

V2 introduced the all-clear branch plus the clarification-answer grounding and the expanded doctor-kit response shape. It still relied on the older summary/next-steps/doctor-kit framing rather than the richer verification task used in V5.

## V1 prompt template

```text
You are a compassionate medical AI assistant. A user completed a fatigue and energy assessment. Your role is to provide personalized, empathetic insights that help them understand their results and prepare for a doctor visit.

USER'S REPORTED SYMPTOMS AND HISTORY:
${symptomsText}

TOP-3 FLAGGED CONDITIONS (ML model, P >= ${mlThresholdPercent}%):
${flaggedAreasText}

Respond with a JSON object using exactly this structure — no markdown, no extra text:
{
  "personalizedSummary": "2–3 sentences speaking directly to this user about what their specific symptom pattern suggests. Be personal and reference what they actually reported.",
  "insights": [
    {
      "diagnosisId": "use the exact id matching one of the flagged conditions above",
      "personalNote": "1–2 sentences explaining why this area is relevant specifically to this user's profile and history."
    }
  ],
  "nextSteps": "2–3 concrete, actionable sentences about what this user should prioritise when speaking with their doctor, based on their specific situation."
}
```

## Safety-tone layer note

This repo contains a Groq safety-tone rewrite layer via `frontend/app/api/safety-rewrite/route.ts`.

- Model: `llama-3.1-8b-instant`
- Timeout target: 5 seconds
- Temperature: `0.2`
- Max tokens: `1000`
- Purpose: rewrite user-facing narrative fields into safer, less diagnostic language
- Deployment intent: graceful fallthrough, so the MedGemma pipeline never blocks if Groq is unavailable

## Historical notes restored

These were the useful interpretation notes from the earlier changelog style and are preserved here so the progression is still easy to read:

### What was weak before V4

- The prompt was duplicated across route files, making it harder to version and compare.
- It asked for specific tests but did not explicitly forbid tests unrelated to the flagged evidence.
- It discouraged generic filler, but did not explicitly forbid introducing extra conditions.
- Safety guidance was present, but certainty calibration could still be sharper.

### What V4 improved

- Centralized all prompt text in one file for easier iteration.
- Added explicit grounding rules for conditions and tests.
- Told the model to describe weaker candidates as lower-priority rather than sounding certain.
- Kept the response format unchanged, so the frontend contract stayed stable.

### What to evaluate next

- Parse success rate
- Hallucinated condition rate
- Hallucinated test rate
- Tone safety / alarmism
- Perceived usefulness of doctor-facing questions and arguments
