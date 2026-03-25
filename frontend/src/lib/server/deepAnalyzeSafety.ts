import { validateDeepAnalyzeSchema, type DeepAnalyzeResult } from '@/lib/medgemma-safety';

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL = 'llama-3.1-8b-instant';

const SAFETY_SYSTEM_PROMPT = `You are a medical communication safety filter. Rewrite only the user-facing narrative fields so they stay warm, non-diagnostic, and appropriately uncertain.

Rules:
- Never say a diagnosis is confirmed unless the input explicitly says it is already medically confirmed
- Use possibility framing such as "may suggest", "could indicate", and "worth discussing with your doctor"
- Remove alarmist wording
- Keep the same overall meaning, specificity, and structure
- Rewrite these fields when present: personalizedSummary, insights[].personalNote, nextSteps, doctorKitSummary, recommendedDoctors[].reason, doctorKits[].openingSummary
- Do not modify immutable fields such as diagnosisId, doctorKitQuestions, doctorKitArguments, suggestedTests, concerningSymptoms, discussionPoints, priority, specialty
- Return valid JSON only, same schema as input`;

function parseJsonObject(raw: string): Record<string, unknown> | null {
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) return null;
  try {
    return JSON.parse(jsonMatch[0]) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function mergeWithImmutableFields(
  original: DeepAnalyzeResult,
  rewritten: DeepAnalyzeResult,
): DeepAnalyzeResult {
  return {
    ...original,
    personalizedSummary: rewritten.personalizedSummary,
    insights: original.insights.map((item, index) => ({
      diagnosisId: item.diagnosisId,
      personalNote: rewritten.insights[index]?.personalNote?.trim() || item.personalNote,
    })),
    nextSteps: rewritten.nextSteps,
    doctorKitSummary: rewritten.doctorKitSummary ?? original.doctorKitSummary,
    doctorKitQuestions: original.doctorKitQuestions,
    doctorKitArguments: original.doctorKitArguments,
    recommendedDoctors: original.recommendedDoctors.map((doctor, index) => ({
      ...doctor,
      reason: rewritten.recommendedDoctors[index]?.reason?.trim() || doctor.reason,
    })),
    doctorKits: original.doctorKits.map((kit, index) => ({
      ...kit,
      openingSummary: rewritten.doctorKits[index]?.openingSummary?.trim() || kit.openingSummary,
    })),
    allClear: original.allClear,
  };
}

export async function rewriteDeepAnalyzeTone(
  report: DeepAnalyzeResult,
): Promise<DeepAnalyzeResult> {
  const groqKey = process.env.GROQ_API_KEY;
  if (!groqKey) return report;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const groqResponse = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${groqKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: GROQ_MODEL,
        messages: [
          { role: 'system', content: SAFETY_SYSTEM_PROMPT },
          { role: 'user', content: JSON.stringify(report) },
        ],
        max_tokens: 1000,
        temperature: 0.2,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    if (!groqResponse.ok) return report;

    const groqData = await groqResponse.json();
    const content: string = groqData.choices?.[0]?.message?.content ?? '';
    const parsed = parseJsonObject(content);
    if (!parsed) return report;

    const validation = validateDeepAnalyzeSchema(parsed);
    if (!validation.ok) return report;

    return mergeWithImmutableFields(report, validation.data);
  } catch {
    return report;
  }
}
