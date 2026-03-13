import { NextRequest, NextResponse } from 'next/server';
import { formatAnswers } from '@/src/lib/formatAnswers';

const HF_MODEL = 'google/medgemma-1.5-4b-it';
const HF_API_URL = process.env.HF_ENDPOINT_URL
  ? `${process.env.HF_ENDPOINT_URL}/v1/chat/completions`
  : 'https://router.huggingface.co/v1/chat/completions';

export async function POST(req: NextRequest) {
  const hfToken = process.env.HF_API_TOKEN;
  if (!hfToken || hfToken === 'hf_your_token_here') {
    return NextResponse.json({ error: 'HF_API_TOKEN is not configured.' }, { status: 500 });
  }

  const body = await req.json();
  const answers: Record<string, unknown> = body.answers ?? {};
  const diagnoses: Array<{ id: string; title: string; signal: string }> = body.diagnoses ?? [];

  const symptomsText = formatAnswers(answers);
  const diagnosisText = diagnoses.map((d) => `- ${d.title} (${d.signal} signal)`).join('\n');

  const prompt = `You are a medical AI assistant. A patient completed a fatigue assessment. Your job is to identify the most likely diagnoses and ask exactly 3 targeted questions to confirm or rule them out.

══ WHAT WE ALREADY KNOW (DO NOT ask about these) ══
${symptomsText}

══ CLINICAL AREAS FLAGGED ══
${diagnosisText || '- No specific areas flagged yet'}

══ YOUR TASK ══
Step 1 — Name 2–3 specific medical hypotheses (e.g. "Perimenopause", "Iron-deficiency anaemia", "Hypothyroidism", "Long COVID / ME-CFS", "Major depressive episode", "Sleep apnoea", "Adrenal fatigue / HPA dysregulation").

Step 2 — For EACH key hypothesis, identify the single most important piece of information that is NOT yet known and would confirm or rule it out.

Step 3 — Write one conversational question per key gap. Rules:
  • Friendly, non-clinical language — the patient is not a doctor
  • Never ask something already answered above
  • Never ask generic time questions like "How long have you had these symptoms?" or "What makes it better or worse?"
  • Each question must be clearly tied to a specific hypothesis

EXAMPLE (for a 45-year-old woman with fatigue + mood changes):
  BAD: "How long have you been feeling tired?" (generic — not tied to any hypothesis)
  GOOD: "Have you noticed any hot flashes, night sweats, or changes in your period lately?" (targets Perimenopause)
  GOOD: "Do you eat red meat, or have you had heavy periods recently?" (targets Iron-deficiency anaemia)
  GOOD: "Do you feel cold when others around you are warm, and has your weight changed without changing what you eat?" (targets Hypothyroidism)

Respond with valid JSON only — no markdown, no preamble, no extra text:
{
  "hypotheses": [
    "Short hypothesis label + brief rationale, e.g. Perimenopause — fatigue and mood shifts in likely 40s woman"
  ],
  "questions": [
    "Conversational question 1",
    "Conversational question 2",
    "Conversational question 3"
  ],
  "questionTargets": [
    "Short hypothesis name this question targets, e.g. Perimenopause",
    "Short hypothesis name this question targets, e.g. Iron deficiency",
    "Short hypothesis name this question targets, e.g. Hypothyroidism"
  ]
}`;

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
        max_tokens: 700,
        temperature: 0.4,
      }),
    });

    if (!hfResponse.ok) {
      const errText = await hfResponse.text();
      return NextResponse.json(
        { error: `MedGemma API error (${hfResponse.status}): ${errText}` },
        { status: hfResponse.status }
      );
    }

    const data = await hfResponse.json();
    const content: string = data.choices?.[0]?.message?.content ?? '';

    // Extract JSON from response (model may wrap it in markdown)
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return NextResponse.json(
        { error: 'Could not parse model response as JSON', raw: content },
        { status: 500 }
      );
    }

    const parsed = JSON.parse(jsonMatch[0]) as {
      hypotheses?: unknown;
      questions?: unknown;
      questionTargets?: unknown;
    };

    // Validate and normalize shape
    const hypotheses = Array.isArray(parsed.hypotheses)
      ? (parsed.hypotheses as string[]).slice(0, 3)
      : [];
    const questions = Array.isArray(parsed.questions)
      ? (parsed.questions as string[]).slice(0, 3)
      : [];
    const questionTargets = Array.isArray(parsed.questionTargets)
      ? (parsed.questionTargets as string[]).slice(0, 3)
      : [];

    // Pad targets to match questions length (model may omit some)
    while (questionTargets.length < questions.length) {
      questionTargets.push('');
    }

    return NextResponse.json({ hypotheses, questions, questionTargets });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
