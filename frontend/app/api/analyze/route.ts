import { NextRequest, NextResponse } from 'next/server';
import { formatAnswersV2 } from '@/src/lib/formatAnswers';
import { writeLog } from '@/src/lib/logger';
import { selectTopConditions, ML_THRESHOLD } from '@/src/lib/mlConfig';

export const maxDuration = 60;

const HF_MODEL = 'google/medgemma-1.5-4b-it';
const HF_API_URL = process.env.HF_ENDPOINT_URL
  ? `${process.env.HF_ENDPOINT_URL}/v1/chat/completions`
  : 'https://router.huggingface.co/v1/chat/completions';

export async function POST(req: NextRequest) {
  const hfToken = process.env.HF_API_TOKEN;
  if (!hfToken || hfToken === 'hf_your_token_here') {
    return NextResponse.json(
      { error: 'HF_API_TOKEN is not configured. Set it in .env.local.' },
      { status: 500 }
    );
  }

  const body = await req.json();
  const answers: Record<string, unknown> = body.answers ?? {};
  const mlScores: Record<string, number> | undefined = body.mlScores;

  const symptomsText = formatAnswersV2(answers);
  const topConditions = mlScores ? selectTopConditions(mlScores) : [];
  const flaggedAreasText = topConditions.length > 0
    ? topConditions.map(([c, p]) => `- ${c}: ${(p * 100).toFixed(1)}%`).join('\n')
    : '- None';

  const prompt = `You are a compassionate medical AI assistant. A user completed a fatigue and energy assessment. Your role is to provide personalized, empathetic insights that help them understand their results and prepare for a doctor visit.

USER'S REPORTED SYMPTOMS AND HISTORY:
${symptomsText}

TOP-3 FLAGGED CONDITIONS (ML model, P ≥ ${ML_THRESHOLD * 100}%):
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

Include one insight for each flagged condition above.`;

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
        max_tokens: 900,
        temperature: 0.3,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    if (!hfResponse.ok) {
      const errText = await hfResponse.text();
      return NextResponse.json(
        { error: `HuggingFace API error (${hfResponse.status}): ${errText}` },
        { status: hfResponse.status }
      );
    }

    const data = await hfResponse.json();
    const content: string = data.choices?.[0]?.message?.content ?? '';

    // Strip markdown code fences if the model wraps output in them
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return NextResponse.json(
        { error: 'Could not parse model response as JSON', raw: content },
        { status: 500 }
      );
    }

    const parsed = JSON.parse(jsonMatch[0]);
    writeLog('analyze', { answers, mlScores, topConditions, result: parsed });
    return NextResponse.json(parsed);
  } catch (err) {
    writeLog('analyze_error', { answers, mlScores, error: String(err) });
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
