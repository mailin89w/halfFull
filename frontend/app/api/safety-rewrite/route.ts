import { NextRequest, NextResponse } from 'next/server';
import { validateDeepAnalyzeSchema } from '@/lib/medgemma-safety';
import type { DeepAnalyzeResult } from '@/lib/medgemma-safety';

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL = 'llama-3.1-8b-instant';

const SAFETY_SYSTEM_PROMPT = `You are a medical communication safety filter. Your only job is to rewrite the provided text fields to ensure they are safe, non-diagnostic, and appropriately uncertain in tone.

Rules:
- Never say "you have", "you are diagnosed with", "you suffer from", or any variant that states a diagnosis as fact
- Replace certainty with possibility: "may suggest", "could indicate", "worth discussing with your GP"
- Never use alarming language. Keep tone warm, supportive, and empowering
- Always frame conditions as things to explore with a doctor, never as confirmed findings
- Add "This is not a medical diagnosis" disclaimer naturally into personalizedSummary if not already present
- Rewrite only: personalizedSummary, insights[].personalNote, nextSteps, doctorKitSummary
- Do NOT change: diagnosisId, doctorKitQuestions, doctorKitArguments
- Return valid JSON only, same schema as input, no markdown, no preamble`;

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
    insights: original.insights.map((item, i) => ({
      diagnosisId: item.diagnosisId,
      personalNote: rewritten.insights[i]?.personalNote?.trim() || item.personalNote,
    })),
    nextSteps: rewritten.nextSteps,
    doctorKitSummary: rewritten.doctorKitSummary,
    doctorKitQuestions: original.doctorKitQuestions,
    doctorKitArguments: original.doctorKitArguments,
    allClear: original.allClear,
  };
}

export async function POST(req: NextRequest) {
  const groqKey = process.env.GROQ_API_KEY;
  if (!groqKey) {
    return NextResponse.json({ error: 'GROQ_API_KEY is not configured.' }, { status: 500 });
  }

  const body = await req.json();
  const candidate = (body?.report ?? body) as Record<string, unknown>;
  const inputValidation = validateDeepAnalyzeSchema(candidate);
  if (!inputValidation.ok) {
    return NextResponse.json(
      { error: 'invalid_input_schema', detail: inputValidation.reason },
      { status: 400 },
    );
  }

  try {
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
          { role: 'user', content: JSON.stringify(inputValidation.data) },
        ],
        max_tokens: 1000,
        temperature: 0.2,
      }),
    });

    if (!groqResponse.ok) {
      const errText = await groqResponse.text();
      return NextResponse.json(
        { error: `Groq API error (${groqResponse.status}): ${errText}` },
        { status: groqResponse.status },
      );
    }

    const groqData = await groqResponse.json();
    const content: string = groqData.choices?.[0]?.message?.content ?? '';
    const parsed = parseJsonObject(content);
    if (!parsed) {
      return NextResponse.json(
        { error: 'Could not parse Groq response as JSON', raw: content },
        { status: 422 },
      );
    }

    const outputValidation = validateDeepAnalyzeSchema(parsed);
    if (!outputValidation.ok) {
      return NextResponse.json(
        { error: 'invalid_output_schema', detail: outputValidation.reason, raw: content },
        { status: 422 },
      );
    }

    const merged = mergeWithImmutableFields(inputValidation.data, outputValidation.data);
    return NextResponse.json(merged);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
