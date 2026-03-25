import { EVALUATED_FATIGUE_DISEASES } from '@/src/lib/assessmentPromptContext';

const CONDITION_ALLOWLIST = 'iron|thyroid|sleep|vitamins|stress|postviral|anemia|iron_deficiency|kidney|sleep_disorder|liver|prediabetes|inflammation|electrolytes|hepatitis|perimenopause';

export const MEDGEMMA_JSON_SYSTEM_V1 =
  'You output valid JSON only. No markdown, no thinking, no explanations, no preamble. Start your response immediately with { and end with }.';

type DeepAnalyzePromptArgs = {
  symptomsText: string;
  flaggedAreasText: string;
  answeredQuestionsText: string;
  uploadedLabsText: string;
  bayesianEvidenceText: string;
  structuredAnswersJson: string;
  scoreSummaryJson: string;
  prioritizedConditions: string[];
  confirmedConditions: string[];
  fatigueSeverity: number | null;
  knnLabText?: string | null;
};

function formatEvaluatedDiseaseList(): string {
  return EVALUATED_FATIGUE_DISEASES
    .map((disease) => `- ${disease.label} (${disease.id})`)
    .join('\n');
}

function buildDetailInstruction(fatigueSeverity: number | null): string {
  if (fatigueSeverity === 3) {
    return 'The patient reported the highest fatigue severity on dpq040. Be especially thorough, specific, and careful about prioritising the symptoms and investigations most worth discussing with a doctor.';
  }
  if (fatigueSeverity === 0) {
    return 'The patient reported no recent tiredness on dpq040. If the rest of the evidence is also weak, keep the response lightweight and prevention-oriented rather than creating unnecessary concern.';
  }
  return 'Use a balanced level of detail that matches the symptom burden shown in the assessment.';
}

function buildCandidateInstruction(prioritizedConditions: string[]): string {
  if (prioritizedConditions.length === 0) {
    return 'No disease cleared the current filtering threshold. It is acceptable to return no suspected disease and mark the result as allClear if the evidence stays weak after review.';
  }

  return `These disease hypotheses cleared the current filtering layer and need verification against the full user evidence:\n${prioritizedConditions.map((id) => `- ${id}`).join('\n')}\n\nFor each one, explicitly decide whether the suspicion is supported by the user evidence or should be declined. Keep at most 3 supported disease hypotheses in the final output.`;
}

export function buildAnalyzePrompt({
  symptomsText,
  flaggedAreasText,
  mlThresholdPercent,
}: {
  symptomsText: string;
  flaggedAreasText: string;
  mlThresholdPercent: number;
}): string {
  return `You are a compassionate medical AI assistant for a fatigue screening product. Personalize every sentence to the user's actual answers.

USER'S REPORTED SYMPTOMS AND HISTORY:
${symptomsText}

TOP-3 FLAGGED CONDITIONS (ML model, P >= ${mlThresholdPercent}%):
${flaggedAreasText}

Respond with valid JSON only. No markdown, no extra text:
{
  "personalizedSummary": "2-3 sentences speaking directly to this user about what their specific symptom pattern may suggest. Reference what they actually reported and include a brief screening-tool disclaimer.",
  "insights": [
    {
      "diagnosisId": "use the exact id matching one of the flagged conditions above",
      "personalNote": "1-2 sentences explaining why this area is relevant specifically to this user's profile and history."
    }
  ],
  "nextSteps": "2-3 concrete, actionable sentences about what this user should prioritise when speaking with their doctor, based on their specific situation."
}

Rules:
- Include one insight for each flagged condition above.
- Only use diagnosisId values that appear in the flagged conditions list above.
- Refer to possibilities, not confirmed diagnoses.
- Keep the tone calm, supportive, and specific.`;
}

export function buildDeepAnalyzePrompt({
  symptomsText,
  flaggedAreasText,
  answeredQuestionsText,
  uploadedLabsText,
  bayesianEvidenceText,
  structuredAnswersJson,
  scoreSummaryJson,
  prioritizedConditions,
  confirmedConditions,
  fatigueSeverity,
  knnLabText,
}: DeepAnalyzePromptArgs): string {
  const evaluatedDiseases = formatEvaluatedDiseaseList();
  const detailInstruction = buildDetailInstruction(fatigueSeverity);
  const candidateInstruction = buildCandidateInstruction(prioritizedConditions);
  const confirmedText = confirmedConditions.length > 0
    ? confirmedConditions.join(', ')
    : 'None reported as already confirmed.';

  return `You are MedGemma acting as a medical screening synthesis assistant for a fatigue assessment product.

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
      "diagnosisId": "exact id from: ${CONDITION_ALLOWLIST}",
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

Rules:
- insights: keep only supported disease suspicions after verification. Maximum 3 items. It is valid to return [].
- If no supported disease suspicion remains, set "allClear": true, return [] for insights, and keep recommendedDoctors and doctorKits empty unless a confirmed condition still makes follow-up reasonable.
- Never invent a disease outside this allowlist: ${CONDITION_ALLOWLIST}.
- Only discuss conditions that are supported by the supplied user answers, uploaded labs, Bayesian evidence, or already confirmed conditions.
- Do not mention clarification questions or ask for more information.
- Keep personalizedSummary as one unified section, not separate mini-sections.
- Make nextSteps doctor-focused, not just test-focused.
- recommendedDoctors: 0 to 3 items maximum.
- doctorKits: create one kit per recommended doctor, same order, up to 3 total.
- Every doctor reason and kit must be customized to this case and mention why that doctor is relevant.
- In doctorKits.concerningSymptoms, list symptoms and patterns, not tests.
- In doctorKits.discussionPoints, combine smart questions with evidence-based reasoning for why deeper evaluation may be justified.
- Never state or imply that a disease is confirmed unless it appears in ALREADY CONFIRMED CONDITIONS.
- For unconfirmed disease suspicions, always use uncertainty language such as "may suggest", "could indicate", or "worth ruling out".
- Never use alarming language.
- Complete the full JSON without truncating.`;
}

export function buildAllClearPrompt({
  symptomsText,
  answeredQuestionsText,
  uploadedLabsText,
}: {
  symptomsText: string;
  answeredQuestionsText: string;
  uploadedLabsText: string;
}): string {
  return `You are a warm, supportive wellness AI. The patient completed a fatigue screening and no significant risk areas were flagged.

PATIENT DATA:
${symptomsText}

ANSWERED QUESTION DICTIONARY:
${answeredQuestionsText}

UPLOADED LABS:
${uploadedLabsText}

Respond with valid JSON only. No markdown, no preamble:
{
  "personalizedSummary": "Up to 6 sentences. Acknowledge the patient's effort, explain that the current screening looks reassuring, mention any positive patterns or low-risk context that supports that, and include a brief disclaimer that this is a screening tool.",
  "insights": [],
  "nextSteps": "Up to 4 sentences focused on staying healthy, what to monitor if they are curious, and when to raise fatigue concerns with a doctor if symptoms change.",
  "doctorKitSummary": "1-2 first-person sentences the patient can use if they still want to discuss wellness with a doctor.",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [],
  "doctorKits": [],
  "allClear": true
}

Rules:
- Warm, positive tone throughout. Never create concern where none exists.
- Do not invent conditions, red flags, or diagnostic urgency.
- Keep the answer lightweight when the fatigue signal is low.
- Complete the full JSON without truncating.`;
}
