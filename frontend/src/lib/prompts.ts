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

// ─── V6: MedGemma Grounding Prompt (Call 1 — clinical evidence only) ──────────

export type MedGemmaGroundingPromptArgs = {
  answeredQuestionsText: string;
  bayesianEvidenceText: string;
  scoreSummaryJson: string;
  prioritizedConditions: string[];
  confirmedConditions: string[];
  riskCalibrationText?: string | null;
  knnLabText?: string | null;
};

export function buildMedGemmaGroundingPromptV6({
  answeredQuestionsText,
  bayesianEvidenceText,
  scoreSummaryJson,
  prioritizedConditions,
  confirmedConditions,
  riskCalibrationText,
  knnLabText,
}: MedGemmaGroundingPromptArgs): string {
  const evaluatedDiseases = formatEvaluatedDiseaseList();
  const confirmedText =
    confirmedConditions.length > 0 ? confirmedConditions.join(', ') : 'None.';
  const candidateList =
    prioritizedConditions.length > 0
      ? prioritizedConditions.map((id) => `- ${id}`).join('\n')
      : '(none — if all evidence is weak, return empty supportedSuspicions)';

  return `You are MedGemma acting as a clinical synthesis engine for a fatigue screening product.

TASK: Produce a complete structured clinical summary. A general-purpose language model will later translate your output into patient-facing prose — it will not have access to the raw patient data, only your JSON. Everything clinically meaningful must therefore be in your output: which symptoms matter, which tests to request, which specialists to see, what to discuss. Do NOT write narrative prose yourself. Produce structured JSON only.

CRITICAL INSTRUCTION: Follow the evidence in this patient record. Do not apply your prior beliefs about which diseases are statistically common. If the questionnaire answers and Bayesian data do not independently support a hypothesis beyond just the ML score, decline it — even if it is a common disease. Your job is to follow the evidence, not your priors.

We tested 11 diseases as fatigue signals:
${evaluatedDiseases}

These hypotheses cleared the ML filtering layer and require verification:
${candidateList}

ALREADY CONFIRMED CONDITIONS (treat as established facts, do not re-evaluate):
${confirmedText}

PATIENT QUESTIONNAIRE ANSWERS:
${answeredQuestionsText}

BAYESIAN CLARIFICATION EVIDENCE:
${bayesianEvidenceText}

ML SCORE SUMMARY:
${scoreSummaryJson}
${riskCalibrationText ? `\nRISK CALIBRATION SNAPSHOT:\n${riskCalibrationText}` : ''}
${knnLabText ? `\nNEAREST-NEIGHBOUR LAB SIGNALS:\n${knnLabText}` : ''}

Decision procedure — follow exactly in order:
1. For each filtered hypothesis, ask: "Does the questionnaire evidence OR Bayesian answers independently support this — beyond just the ML score?"
   - If YES: add to supportedSuspicions. Include the specific symptoms from this record that support it and the specific tests that would confirm or rule it out.
   - If NO: add to declinedSuspicions with a one-phrase reason naming the missing or contradictory evidence.
2. For each supportedSuspicion, decide which specialist should address it and what they need to hear. Populate recommendedSpecialties (0–3). If supportedSuspicions is empty, recommendedSpecialties must also be empty.
3. Scan for any symptom that could be explained by a medication rather than a disease process; log in medicationFlags.
4. Use the risk calibration snapshot to calibrate your confidence and prioritization:
   - urgent = prompt medical follow-up should be easier to justify when the record supports it
   - high confidence = evidence sources agree, so you can be more decisive while still using uncertainty language
   - low confidence = keep the suspicion lightweight unless the direct evidence is strong
   - score_suppressed = upstream gating/Bayesian review reduced the effective score, so do not overstate that hypothesis unless the record strongly supports it anyway

Respond with valid JSON only. No markdown, no preamble, no narrative prose:
{
  "supportedSuspicions": [
    {
      "diagnosisId": "exact id from: ${CONDITION_ALLOWLIST}",
      "confidence": "probable | possible | worth_ruling_out",
      "anchorEvidence": "One specific questionnaire answer or Bayesian feature from this record that supports the hypothesis.",
      "reasoning": "1-2 sentences citing specific evidence from this record. Do not repeat statistical priors.",
      "keySymptoms": [
        "Specific symptom or finding from this patient's answers that supports this condition — quoted from the evidence, not paraphrased generically"
      ],
      "recommendedTests": [
        "Specific test that would confirm or rule out this condition for this patient"
      ]
    }
  ],
  "declinedSuspicions": [
    {
      "diagnosisId": "exact id from: ${CONDITION_ALLOWLIST}",
      "reason": "One sentence naming what evidence was expected but absent or contradicted by the record."
    }
  ],
  "medicationFlags": [
    {
      "labOrSymptom": "name of the lab or symptom",
      "medication": "medication name",
      "note": "One sentence explaining how this medication may affect the signal."
    }
  ],
  "recommendedSpecialties": [
    {
      "specialty": "GP | Endocrinologist | Sleep specialist | Nephrologist | Hepatologist | Gynaecologist | Rheumatologist | Haematologist | other relevant specialist",
      "priority": "start_here | consider_next | specialist_if_needed",
      "clinicalReason": "1-2 sentences explaining why this specialty is needed for this patient's supported suspicions — cite the specific conditions or symptoms.",
      "symptomsToRaise": [
        "Specific symptom or finding from this patient's evidence that this specialist needs to hear"
      ],
      "testsToRequest": [
        "Specific test or referral this specialist should be asked about"
      ],
      "discussionPoints": [
        "Specific clinical question or evidence-based argument this patient should raise with this specialist. Must cite a specific finding from this record. Not a generic question."
      ]
    }
  ]
}

Rules:
- supportedSuspicions: 0 to 3 items. Returning [] is valid and correct if evidence is weak.
- Never invent a diagnosisId outside the allowlist: ${CONDITION_ALLOWLIST}.
- Every diagnosisId listed under "These hypotheses cleared the ML filtering layer" must end up in either supportedSuspicions or declinedSuspicions. Do not silently drop any candidate.
- keySymptoms must come from this patient's actual answers — no invented symptoms.
- recommendedTests must be tied to a supportedSuspicion — no generic panels.
- recommendedSpecialties: 0 to 3. Must be empty if supportedSuspicions is empty.
- MINIMUM RULE: If supportedSuspicions is non-empty, include at least 1 recommendedSpecialty.
- discussionPoints must cite a specific finding from this record — no generic questions like "ask about blood tests".
- Do not write personalizedSummary, nextSteps, doctorKitSummary, or any narrative prose.
- Complete the full JSON without truncating.`;
}

// ─── V6: Groq Synthesis Prompt (Call 2 — full narrative) ──────────────────────

export type GroqSynthesisPromptArgs = {
  groundingResultJson: string;
  fatigueSeverity: number | null;
  riskCalibrationText?: string | null;
  overallUrgency?: 'routine' | 'soon' | 'urgent';
  oneShot?: string | null;
};

export function buildGroqSynthesisPromptV6({
  groundingResultJson,
  fatigueSeverity,
  riskCalibrationText,
  overallUrgency = 'routine',
  oneShot,
}: GroqSynthesisPromptArgs): string {
  const detailInstruction = buildDetailInstruction(fatigueSeverity);
  const toneInstruction =
    overallUrgency === 'urgent'
      ? 'Tone calibration: stay calm and supportive, but be more explicit that prompt medical follow-up matters for the highest-risk items. Do not sound panicked or diagnostic.'
      : overallUrgency === 'soon'
        ? 'Tone calibration: stay calm and supportive, while clearly encouraging near-term follow-up for the stronger signals.'
        : 'Tone calibration: stay calm, supportive, and non-urgent. Do not create unnecessary alarm.';

  return `You are a medical communication writer. A clinical AI has produced a structured medical summary for a patient. Your job is to translate that clinical summary into warm, clear, first-person patient-facing text.

YOUR ROLE IS PROSE TRANSLATION ONLY. Do not add conditions, symptoms, tests, doctors, or discussion points that are not already in the clinical evidence below. Do not perform your own medical reasoning. Every piece of medical content in your output must come directly from the clinical evidence JSON.

${detailInstruction}
${toneInstruction}

SECTION ROLE ASSIGNMENT — each section answers a different question. Strictly enforce — no cross-section repetition:
- summaryPoints / personalizedSummary: "What is this person experiencing?" — symptom picture and patterns ONLY. Do not name conditions, tests, or doctors here.
- insights[].personalNote: "Why was this condition flagged for this specific patient?" — clinical evidence link only. Do not restate symptoms already in the summary.
- nextSteps: "Who to see first, in what order, and why — in 2 sentences." No symptom descriptions. No condition reasoning. Pure action sequence.
- doctorKits: "What to say, bring, and ask at each specific appointment." Actionable and appointment-ready. Do not re-summarise conditions or symptoms.

SPECIALIST RULE: recommendedDoctors must always include at least one non-GP specialist when supportedSuspicions is non-empty. Patients may have already seen their GP — always give them a specialist path they may not have explored yet (e.g. Endocrinologist, Haematologist, Gynaecologist, Sleep specialist, Rheumatologist, Hepatologist, Nephrologist).

CLINICAL EVIDENCE (source of all medical content — use only what is here):
${groundingResultJson}

${riskCalibrationText ? `RISK CALIBRATION SNAPSHOT:\n${riskCalibrationText}\n` : ''}Use the risk calibration snapshot to tune language:
- urgent items: be clearer that prompt review is appropriate
- soon items: encourage near-term booking
- routine items: keep the framing light
- low confidence items: use softer uncertainty language
- high confidence items: clearer explanation is allowed, but still never imply diagnosis
- if a condition is marked score_suppressed, do not over-emphasize it unless the clinical evidence strongly supports it

${oneShot ? `EXAMPLE OF A PERFECT OUTPUT (follow this quality and structure, applied to the clinical evidence above):\n${oneShot}\n` : ''}Respond with valid JSON only. No markdown, no preamble:
{
  "summaryPoints": [
    "4-6 bullet strings. Each describes one specific aspect of what this patient is experiencing — a symptom, pattern, severity, or duration. No conditions named. No tests. Pure symptom picture drawn from keySymptoms in the clinical evidence.",
    "Example: 'Severe fatigue at 3/3 intensity for the past 3 months, worst in the mornings'",
    "Example: 'Heavy periods lasting 8 days with clotting, consistent for 6+ months'",
    "Example: 'Waking 3 times per night on an average of 5.5 hours of sleep'",
    "Example: 'Cold intolerance in hands and feet even in warm environments'",
    "Example: 'Concentration and memory difficulties affecting work performance'"
  ],
  "personalizedSummary": "1-2 sentence prose version of the above bullets, plus a screening-tool disclaimer. This is the fallback when bullets are not rendered.",
  "declinedSuspicions": [
    {
      "diagnosisId": "copy every declined diagnosisId from the clinical evidence",
      "reason": "translate the declined reason into concise patient-friendly language without adding new medical claims"
    }
  ],
  "insights": [
    {
      "diagnosisId": "exact id from supportedSuspicions in the clinical evidence — no others",
      "confidence": "copy the confidence value from the clinical evidence",
      "personalNote": "2-3 sentences. Translate the reasoning and anchorEvidence for this suspicion into patient-friendly language. Do NOT restate the symptoms already covered in summaryPoints."
    }
  ],
  "recoveryOutlook": "2-3 sentences. Explain what improvement may depend on in this case, what is treatable or investigable first, and how quickly people often start getting clarity once the right doctor and tests are involved. Keep it realistic and non-diagnostic.",
  "nextSteps": "2 sentences maximum. Who to see first and why (from recommendedSpecialties[0].clinicalReason), then who second. No symptom descriptions. No condition explanations.",
  "doctorKitSummary": "2 first-person sentences. An opening statement this patient can read at any of the recommended appointments. Draw from keySymptoms — make it specific to this patient.",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [
    {
      "specialty": "copy from recommendedSpecialties[].specialty in the clinical evidence — no new specialties",
      "priority": "copy from recommendedSpecialties[].priority",
      "reason": "1-2 sentences. Why this specific specialty for this specific patient. Draw from clinicalReason. No symptom list here.",
      "symptomsToDiscuss": [
        "Copy each item from symptomsToRaise in the matching recommendedSpecialties entry. Keep as an array and do not leave empty when recommendedSpecialties is non-empty."
      ],
      "suggestedTests": [
        "Copy each item from testsToRequest in the matching recommendedSpecialties entry. Keep as an array and do not leave empty when the matching entry has tests."
      ]
    }
  ],
  "doctorKits": [
    {
      "specialty": "same as the matching recommendedDoctor above",
      "openingSummary": "2 first-person sentences tailored to this specialist. Name the specific conditions suspected and what you want from this doctor.",
      "bringToAppointment": [
        "Practical logistics only: diary, prior results, medication list. No medical content."
      ],
      "concerningSymptoms": [
        "Copy each item from symptomsToRaise in the matching recommendedSpecialties entry. Keep as an array and do not leave empty when recommendedSpecialties is non-empty."
      ],
      "recommendedTests": [
        "Copy each item from testsToRequest in the matching recommendedSpecialties entry. Keep as an array and do not leave empty when the matching entry has tests."
      ],
      "discussionPoints": [
        "Translate each discussionPoints item from the matching recommendedSpecialties entry into first-person patient language. Keep as an array and preserve clinical specificity."
      ],
      "whatToSay": "2 sentences. First-person appointment opener specific to this specialty. State what you suspect and what you want to rule out or confirm."
    }
  ],
  "allClear": false
}

Rules:
- summaryPoints: 4-6 items. Symptoms only. No conditions, tests, or doctors.
- summaryPoints are required. Do not omit them.
- If supportedSuspicions plus declinedSuspicions exist in the clinical evidence, every diagnosisId from both arrays must appear in either insights or declinedSuspicions. Do not silently drop conditions from the clinical evidence.
- insights: one entry per supportedSuspicion. No extras. personalNote must NOT repeat summaryPoints content.
- declinedSuspicions: copy every declined suspicion from the clinical evidence unless the list is empty.
- recoveryOutlook: required. Keep it grounded in the actual supported suspicions and next-step pathway.
- nextSteps: maximum 2 sentences. Action sequence only.
- recommendedDoctors: one per recommendedSpecialty. MUST include at least one non-GP specialist.
- doctorKits: one kit per recommendedDoctor, same order.
- When recommendedSpecialties is non-empty, do not leave symptomsToDiscuss, concerningSymptoms, or discussionPoints empty. Copy or translate the matching array entries.
- Keep suggestedTests and recommendedTests as arrays. If the clinical evidence entry has tests, the output array must preserve them.
- Do NOT add conditions, symptoms, tests, or discussion points not in the clinical evidence.
- For unconfirmed suspicions use: "may suggest", "could indicate", "worth ruling out".
- Never use alarming language.
- If recommendedSpecialties is empty, return [] for both recommendedDoctors and doctorKits.
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
  "summaryPoints": [
    "Exactly 3-5 short bullets, each 4-12 words, grounded in this assessment. No conditions, tests, or doctors."
  ],
  "personalizedSummary": "2-3 sentences. Reference the specific things this person actually mentioned (sleep, energy dips, stress patterns — by name). Do NOT use generic phrases like 'your answers look reassuring'. Instead write something like: 'From what you shared, the tiredness you experience seems connected to [specific pattern] rather than pointing to an underlying condition. The screening didn't flag anything that would need urgent follow-up, which is genuinely good news.' No medical disclaimers in this field. Warm, direct, second-person voice.",
  "declinedSuspicions": [],
  "recoveryOutlook": "2-3 sentences. Keep this light and reassuring. Explain that no major fatigue signal was found and that outlook stays good if symptoms remain mild or stable, while noting when to seek follow-up if things change.",
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
- summaryPoints and recoveryOutlook are required.
- summaryPoints: exactly 3-5 items, each 4-12 words, and each must be a symptom or wellness pattern only.
- personalizedSummary must reference something specific from the answers — not generic.
- Keep the answer lightweight when the fatigue signal is low.
- Complete the full JSON without truncating.`;
}

// ─── V7: Groq Synthesis Prompt (improved personalizedSummary, KNN block, fatigue-severity tone) ──

export type GroqSynthesisPromptV7Args = GroqSynthesisPromptArgs & {
  topBayesianConditions?: string[];
};

export function buildGroqSynthesisPromptV7({
  groundingResultJson,
  fatigueSeverity,
  riskCalibrationText,
  overallUrgency = 'routine',
  oneShot,
  topBayesianConditions,
}: GroqSynthesisPromptV7Args): string {
  const detailInstruction = buildDetailInstruction(fatigueSeverity);

  const toneInstruction =
    overallUrgency === 'urgent'
      ? 'Tone calibration: stay calm and supportive, but be more explicit that prompt medical follow-up matters for the highest-risk items. Do not sound panicked or diagnostic.'
      : overallUrgency === 'soon'
        ? 'Tone calibration: stay calm and supportive, while clearly encouraging near-term follow-up for the stronger signals.'
        : 'Tone calibration: stay calm, supportive, and non-urgent. Do not create unnecessary alarm.';

  const summaryOpeningInstruction =
    fatigueSeverity === 3
      ? 'For personalizedSummary: open with the weight of what they are dealing with. Example opening: "You\'re dealing with persistent, significant fatigue — and from what you shared, this isn\'t a standalone symptom. It seems to overlap with [specific symptoms from keySymptoms]."'
      : fatigueSeverity === 0
        ? 'For personalizedSummary: open gently. Example opening: "You mentioned some tiredness on certain days — and from what else you shared, there are a few patterns worth looking into together."'
        : 'For personalizedSummary: open directly and personally. Example opening: "From what you shared, your fatigue is not a standalone symptom — it\'s worth looking into how it connects with [specific symptoms from keySymptoms]."';

  const bayesianContext = topBayesianConditions && topBayesianConditions.length > 0
    ? `\nHIGHEST BAYESIAN GAIN CONDITIONS (Bayesian follow-up most strongly confirmed these — give them priority in the personalizedSummary):\n${topBayesianConditions.map(c => `- ${c}`).join('\n')}`
    : '';

  return `You are a medical communication writer. A clinical AI has produced a structured medical summary for a patient. Your job is to translate that clinical summary into warm, clear, first-person patient-facing text.

YOUR ROLE IS PROSE TRANSLATION ONLY. Do not add conditions, symptoms, tests, doctors, or discussion points that are not already in the clinical evidence below. Every piece of medical content in your output must come directly from the clinical evidence JSON.

${detailInstruction}
${toneInstruction}
${summaryOpeningInstruction}

CRITICAL INSTRUCTION FOR personalizedSummary:
- Do NOT use generic clinical language ("fatigue may suggest", "potential thyroid abnormalities", "markers could be present").
- Instead, NAME the actual symptoms this person reported. Pull them from keySymptoms arrays in the clinical evidence.
- Connect the dots: show how fatigue overlaps with other specific symptoms (e.g. "the heavy periods you mentioned", "your disrupted sleep schedule", "the night sweats").
- The highest-Bayesian-gain conditions are most worth mentioning by connection.
- Write in warm second person: "from what you shared", "you mentioned", "the [symptom] you described".
- Do NOT include a screening disclaimer in this field. That is handled elsewhere.
- End with: "Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit."
- Maximum 3 sentences.

SECTION ROLE ASSIGNMENT — strictly enforce, no cross-section repetition:
- summaryPoints: "What symptoms or patterns stand out?" — exactly 2-3 very short bullets. Symptoms only. No conditions, diagnoses, tests, or doctors.
- personalizedSummary: "What is this person experiencing and how do their symptoms connect?" — symptom picture only. No conditions, tests, or doctors.
- insights[].personalNote: "Why was this condition flagged for this specific patient?" — clinical evidence link only.
- nextSteps: "Who to see first and why — 2 sentences max." Action only.
- doctorKits: "What to say, bring, and ask at each appointment." Actionable and appointment-ready.

SPECIALIST RULE: recommendedDoctors must always include at least one non-GP specialist when supportedSuspicions is non-empty.

CLINICAL EVIDENCE (source of all medical content):
${groundingResultJson}
${bayesianContext}
${riskCalibrationText ? `\nRISK CALIBRATION SNAPSHOT:\n${riskCalibrationText}\n` : ''}
Use the risk calibration snapshot to tune language:
- urgent items: clearer that prompt review is appropriate
- soon items: encourage near-term booking
- routine items: keep the framing light
- low confidence: softer uncertainty language
- high confidence: clearer explanation allowed, never imply diagnosis
- score_suppressed: do not over-emphasize unless clinical evidence strongly supports it

${oneShot ? `EXAMPLE OF A PERFECT OUTPUT (follow this quality and structure):\n${oneShot}\n` : ''}Respond with valid JSON only. No markdown, no preamble:
{
  "summaryPoints": [
    "Exactly 2-3 bullet strings",
    "Each bullet must be 3-10 words",
    "Each bullet must describe a symptom or pattern only",
    "No conditions, diagnoses, tests, doctors, or generic filler"
  ],
  "personalizedSummary": "2-3 sentences. Open with the personalizedSummary opening instruction above. Name the actual symptoms from keySymptoms. Connect them to fatigue. End with the 'Below you can see...' sentence. No disclaimer.",
  "declinedSuspicions": [
    {
      "diagnosisId": "copy every declined diagnosisId from the clinical evidence",
      "reason": "translate the declined reason into concise patient-friendly language without adding new medical claims"
    }
  ],
  "insights": [
    {
      "diagnosisId": "exact id from supportedSuspicions in the clinical evidence — no others",
      "confidence": "copy the confidence value from the clinical evidence",
      "personalNote": "2-3 sentences. Translate the reasoning and anchorEvidence for this suspicion into patient-friendly language. Do NOT restate symptoms already in personalizedSummary."
    }
  ],
  "recoveryOutlook": "2-3 sentences. What improvement depends on, what is treatable first, how quickly clarity often comes. Realistic and non-diagnostic.",
  "nextSteps": "2 sentences maximum. Who to see first and why, then who second. No symptom descriptions.",
  "doctorKitSummary": "2 first-person sentences. Opening statement for any of the recommended appointments. Specific to this patient.",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [
    {
      "specialty": "copy from recommendedSpecialties in the clinical evidence",
      "priority": "copy from recommendedSpecialties",
      "reason": "1-2 sentences. Why this specialty for this patient specifically.",
      "symptomsToDiscuss": ["copy from symptomsToRaise in the matching entry"],
      "suggestedTests": ["copy from testsToRequest in the matching entry"]
    }
  ],
  "doctorKits": [
    {
      "specialty": "same as the matching recommendedDoctor",
      "openingSummary": "2 first-person sentences tailored to this specialist.",
      "bringToAppointment": ["Practical logistics only: diary, prior results, medication list."],
      "concerningSymptoms": ["copy from symptomsToRaise in the matching entry"],
      "recommendedTests": ["copy from testsToRequest in the matching entry"],
      "discussionPoints": ["translate discussionPoints from the matching entry into first-person patient language"],
      "whatToSay": "2 sentences. First-person appointment opener for this specialty."
    }
  ],
  "allClear": false
}

Rules:
- summaryPoints are required.
- summaryPoints: exactly 2-3 items, each 3-10 words.
- summaryPoints must be concrete symptom or pattern bullets, not prose paragraphs.
- summaryPoints must not mention conditions, diagnoses, tests, doctors, or treatment.
- personalizedSummary: name actual symptoms, connect them, warm tone, end with 'Below you can see...', no disclaimer.
- If supportedSuspicions plus declinedSuspicions exist, every diagnosisId from both must appear in insights or declinedSuspicions.
- insights: one entry per supportedSuspicion. personalNote must NOT repeat personalizedSummary content.
- recoveryOutlook: required only when supportedSuspicions is non-empty. Omit for all-clear.
- nextSteps: maximum 2 sentences. Action sequence only.
- recommendedDoctors: at least one non-GP specialist when supportedSuspicions is non-empty.
- doctorKits: one kit per recommendedDoctor, same order.
- Do NOT add conditions, symptoms, tests not in the clinical evidence.
- For unconfirmed suspicions: "may suggest", "could indicate", "worth ruling out".
- Never use alarming language.
- Complete the full JSON without truncating.`;
}

export function buildGroqSynthesisFallbackPromptV7({
  groundingResultJson,
  overallUrgency = 'routine',
}: Pick<GroqSynthesisPromptV7Args, 'groundingResultJson' | 'overallUrgency'>): string {
  const toneInstruction =
    overallUrgency === 'urgent'
      ? 'Stay calm, but clearly support prompt medical follow-up where the evidence already justifies it.'
      : overallUrgency === 'soon'
        ? 'Stay calm and encourage near-term follow-up for stronger signals.'
        : 'Stay calm, supportive, and non-urgent.';

  return `You are a medical communication writer. Convert the clinical evidence JSON into concise patient-facing JSON.

Do not add medical content that is not already in the clinical evidence.
${toneInstruction}

Clinical evidence JSON:
${groundingResultJson}

Return valid JSON only:
{
  "summaryPoints": [
    "Exactly 2-3 short bullets, each 3-10 words, symptoms or patterns only"
  ],
  "personalizedSummary": "2-3 sentences, warm and specific. Mention actual symptoms only. End with: 'Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.'",
  "declinedSuspicions": [
    { "diagnosisId": "copy from clinical evidence", "reason": "translate briefly" }
  ],
  "insights": [
    { "diagnosisId": "copy from supportedSuspicions", "confidence": "copy confidence", "personalNote": "2 short sentences" }
  ],
  "recoveryOutlook": "2 short sentences.",
  "nextSteps": "2 sentences maximum.",
  "doctorKitSummary": "2 first-person sentences.",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [
    { "specialty": "copy", "priority": "copy", "reason": "1-2 short sentences", "symptomsToDiscuss": ["copy"], "suggestedTests": ["copy"] }
  ],
  "doctorKits": [
    { "specialty": "copy", "openingSummary": "2 first-person sentences", "bringToAppointment": ["practical items"], "concerningSymptoms": ["copy"], "recommendedTests": ["copy"], "discussionPoints": ["translate briefly"], "whatToSay": "2 first-person sentences" }
  ],
  "allClear": false
}

Rules:
- summaryPoints are required: exactly 2-3 items, 3-10 words each.
- summaryPoints must be symptoms/patterns only. No conditions, diagnoses, tests, or doctors.
- Keep every diagnosisId from supportedSuspicions in insights.
- Keep every diagnosisId from declinedSuspicions in declinedSuspicions.
- Do not add new diagnosisIds, symptoms, tests, or specialties.
- Keep arrays short and complete.`;
}
