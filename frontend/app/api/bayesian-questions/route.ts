import { NextRequest, NextResponse } from 'next/server';
import { writeLog } from '@/src/lib/logger';
import { persistHealthSession, readOptionalPrivacyContext, type ServerPrivacyContext } from '@/src/lib/server/privacy';

/**
 * POST /api/bayesian-questions
 *
 * Returns structured follow-up questions for conditions that cleared the
 * ML trigger threshold (default 0.40), plus PHQ-2 / GAD-2 confounder questions.
 *
 * Body: { mlScores: Record<string, number>, patientSex?: string, existingAnswers?: Record<string, unknown> }
 *
 * Response:
 * {
 *   confounderQuestions: BayesianQuestion[],
 *   conditionQuestions:  ConditionQuestion[],
 * }
 */

const _rawBackendUrl = process.env.RAILWAY_API_URL ?? process.env.BACKEND_URL ?? 'http://localhost:8000';
const RAILWAY_URL = _rawBackendUrl.startsWith('http') ? _rawBackendUrl : `https://${_rawBackendUrl}`;

async function callRailway(body: object): Promise<Record<string, unknown>> {
  const res = await fetch(`${RAILWAY_URL}/bayesian/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await res.json() as Record<string, unknown>;

  if (!res.ok || data.error) {
    return { error: String(data.error ?? `Railway returned ${res.status}`) };
  }

  return data;
}

export async function POST(req: NextRequest) {
  let mlScores: Record<string, number>;
  let patientSex: string | undefined;
  let existingAnswers: Record<string, unknown>;
  let privacy: ServerPrivacyContext | null;

  try {
    const body = await req.json() as { mlScores?: unknown; patientSex?: unknown; existingAnswers?: unknown; privacy?: unknown };
    mlScores = (body.mlScores ?? {}) as Record<string, number>;
    patientSex = typeof body.patientSex === 'string' ? body.patientSex : undefined;
    existingAnswers = (body.existingAnswers ?? {}) as Record<string, unknown>;
    privacy = readOptionalPrivacyContext(body.privacy);
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body or consent payload' }, { status: 400 });
  }

  const result = await callRailway({ mode: 'questions', ml_scores: mlScores, patient_sex: patientSex, existing_answers: existingAnswers });

  if (result.error) {
    writeLog('bayesian_questions_error', {
      anonymousId: privacy?.anonymousId ?? null,
      mlScoreKeys: Object.keys(mlScores),
      error: result.error,
    });
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  if (privacy) {
    await persistHealthSession({
      privacy,
      sessionKind: 'bayesian_questions',
      payload: {
        mlScores,
        patientSex,
        existingAnswers,
        result,
      },
      profileSummary: {
        mlScoreKeys: Object.keys(mlScores),
        followUpConditionCount: Array.isArray(result.condition_questions)
          ? result.condition_questions.length
          : 0,
      },
    });
  }

  writeLog('bayesian_questions', {
    anonymousId: privacy?.anonymousId ?? null,
    mlScoreKeys: Object.keys(mlScores),
    followUpConditionCount: Array.isArray(result.condition_questions)
      ? result.condition_questions.length
      : 0,
  });
  return NextResponse.json(result);
}
