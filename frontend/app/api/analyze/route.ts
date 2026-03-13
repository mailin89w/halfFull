import { NextRequest, NextResponse } from 'next/server';
import { formatAnswers } from '@/src/lib/formatAnswers';

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
  const diagnoses: Array<{ id: string; title: string; signal: string }> = body.diagnoses ?? [];

  const symptomsText = formatAnswers(answers);
  const diagnosisText = diagnoses.map((d) => `- ${d.title} (${d.signal} signal)`).join('\n');

  const prompt = `You are a compassionate medical AI assistant. A user completed a fatigue and energy assessment. Your role is to provide personalized, empathetic insights that help them understand their results and prepare for a doctor visit.

USER'S REPORTED SYMPTOMS AND HISTORY:
${symptomsText}

AREAS IDENTIFIED FOR INVESTIGATION (from clinical screening algorithm):
${diagnosisText}

Respond with a JSON object using exactly this structure — no markdown, no extra text:
{
  "personalizedSummary": "2–3 sentences speaking directly to this user about what their specific symptom pattern suggests. Be personal and reference what they actually reported.",
  "insights": [
    {
      "diagnosisId": "use the exact id: iron|thyroid|sleep|vitamins|stress|postviral",
      "personalNote": "1–2 sentences explaining why this area is relevant specifically to this user's profile and history."
    }
  ],
  "nextSteps": "2–3 concrete, actionable sentences about what this user should prioritise when speaking with their doctor, based on their specific situation."
}

Include one insight for each identified area above. Match diagnosisId exactly to one of: iron, thyroid, sleep, vitamins, stress, postviral.`;

  try {
    const hfResponse = await fetch(HF_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${hfToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: HF_MODEL,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 900,
        temperature: 0.3,
      }),
    });

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
    return NextResponse.json(parsed);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
