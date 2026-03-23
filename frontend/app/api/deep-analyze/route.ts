import { NextRequest, NextResponse } from 'next/server';
import { formatAnswersV2 } from '@/src/lib/formatAnswers';
import { writeLog } from '@/src/lib/logger';
import { ML_THRESHOLD, selectTopConditions } from '@/src/lib/mlConfig';

export const maxDuration = 60;

const HF_MODEL = 'google/medgemma-1.5-4b-it';
const HF_API_URL = process.env.HF_ENDPOINT_URL
  ? `${process.env.HF_ENDPOINT_URL}/v1/chat/completions`
  : 'https://router.huggingface.co/v1/chat/completions';

/**
 * Attempts to parse potentially-truncated JSON from MedGemma.
 * Handles: incomplete strings, dangling commas, unclosed arrays/objects.
 */
function repairAndParseJson(raw: string): Record<string, unknown> | null {
  // First try straight parse
  try { return JSON.parse(raw) as Record<string, unknown>; } catch { /* fall through */ }

  // Build a bracket stack to find what needs closing
  let inString = false;
  let escaped = false;
  const stack: string[] = [];

  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (escaped) { escaped = false; continue; }
    if (ch === '\\' && inString) { escaped = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === '{') stack.push('}');
    else if (ch === '[') stack.push(']');
    else if ((ch === '}' || ch === ']') && stack.length > 0) stack.pop();
  }

  // Strip trailing comma / incomplete key-value, close any open string, close open structures
  let trimmed = raw.trimEnd();
  if (inString) trimmed += '"';                    // close dangling string
  trimmed = trimmed.replace(/,\s*$/, '');          // remove trailing comma
  const closing = stack.reverse().join('');

  try { return JSON.parse(trimmed + closing) as Record<string, unknown>; } catch { /* fall through */ }

  // Last resort: find the last valid } and try from the start to there
  for (let end = trimmed.length - 1; end > 1; end--) {
    if (trimmed[end] === '}') {
      try { return JSON.parse(trimmed.slice(0, end + 1)) as Record<string, unknown>; } catch { /* continue */ }
    }
  }

  return null;
}

export async function POST(req: NextRequest) {
  const hfToken = process.env.HF_API_TOKEN;
  if (!hfToken || hfToken === 'hf_your_token_here') {
    return NextResponse.json({ error: 'HF_API_TOKEN is not configured.' }, { status: 500 });
  }

  const body = await req.json();
  const answers: Record<string, unknown> = body.answers ?? {};
  const mlScores: Record<string, number> | undefined = body.mlScores;

  const symptomsText = formatAnswersV2(answers);

  const topConditions = mlScores ? selectTopConditions(mlScores) : [];
  const flaggedConditions = topConditions
    .filter(([, p]) => p >= ML_THRESHOLD)
    .map(([c]) => c);

  const flaggedAreasText = topConditions.length > 0
    ? topConditions
        .map(([condition, prob]) => `- ${condition}: ${(prob * 100).toFixed(1)}%`)
        .join('\n')
    : '- None';

  const prompt = `You are a medical AI generating a personalised fatigue report. Reference the patient's actual symptoms — never give generic advice.

PATIENT DATA:
${symptomsText}

TOP-3 FLAGGED CONDITIONS (ML model, P ≥ ${ML_THRESHOLD * 100}%):
${flaggedAreasText}

Respond with valid JSON only — no markdown, no preamble:
{
  "personalizedSummary": "2 sentences. Name the most likely driver and connect it directly to what this patient reported. Warm, direct tone.",
  "insights": [
    {"diagnosisId": "exact id from: iron|thyroid|sleep|vitamins|stress|postviral|anemia|iron_deficiency|kidney|sleep_disorder|liver|prediabetes|inflammation|electrolytes|hepatitis|perimenopause", "personalNote": "1-2 sentences explaining why THIS flagged area fits this patient's specific reported symptoms."}
  ],
  "nextSteps": "2 sentences. Tell the patient exactly which tests to ask for and why, based on their specific profile.",
  "doctorKitSummary": "2 sentences in first person that the patient reads aloud to open their GP appointment. Must mention their top symptom, how it affects daily life, and what they suspect.",
  "doctorKitQuestions": [
    "Specific assertive question for the GP tied to this patient's top flagged area",
    "Specific question about a second flagged area or next diagnostic step"
  ],
  "doctorKitArguments": [
    "Argument referencing this patient's specific symptoms to justify requesting test 1",
    "Argument referencing this patient's specific symptoms to justify requesting test 2"
  ]
}

Rules:
- insights: one entry per flagged area, max 4 total. Prioritise ML-flagged conditions: ${flaggedConditions.join(', ') || 'none'}.
- doctorKitQuestions: exactly 2 items.
- doctorKitArguments: exactly 2 items.
- Every string must reference THIS patient's data — no generic filler.
- Complete the full JSON without truncating.`;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90_000);
    const hfResponse = await fetch(HF_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${hfToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: HF_MODEL,
        messages: [
          { role: 'system', content: 'You output valid JSON only. No markdown, no thinking, no explanations, no preamble. Start your response immediately with { and end with }.' },
          { role: 'user', content: prompt },
        ],
        max_tokens: 1500,
        temperature: 0.3,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    if (!hfResponse.ok) {
      const errText = await hfResponse.text();
      return NextResponse.json(
        { error: `MedGemma API error (${hfResponse.status}): ${errText}` },
        { status: hfResponse.status }
      );
    }

    const data = await hfResponse.json();
    const content: string = data.choices?.[0]?.message?.content ?? '';

    const jsonMatch = content.match(/\{[\s\S]*/);
    if (!jsonMatch) {
      return NextResponse.json(
        { error: 'Could not parse model response as JSON', raw: content },
        { status: 500 }
      );
    }

    const parsed = repairAndParseJson(jsonMatch[0]);
    if (!parsed) {
      return NextResponse.json(
        { error: 'Could not parse model response as JSON', raw: content },
        { status: 500 }
      );
    }
    writeLog('deep_analyze', { answers, mlScores, topConditions, result: parsed });
    return NextResponse.json(parsed);
  } catch (err) {
    writeLog('deep_analyze_error', { answers, mlScores, error: String(err) });
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
