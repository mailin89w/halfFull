import { NextRequest, NextResponse } from 'next/server';
import { writeLog } from '@/src/lib/logger';
import { persistHealthSession, readOptionalPrivacyContext, type ServerPrivacyContext } from '@/src/lib/server/privacy';

/**
 * POST /api/bayesian-update
 *
 * Runs the Bayesian posterior update given ML scores + user answers.
 *
 * Body:
 * {
 *   mlScores:            Record<string, number>,
 *   confounderAnswers:   Record<string, number>,   // PHQ-2 / GAD-2 ordinal values
 *   answersByCondition:  Record<string, Record<string, string>>,
 *   patientSex?:         string,
 *   existingAnswers?:    Record<string, unknown>,  // raw quiz answers for silent prefill
 * }
 *
 * Response:
 * {
 *   posteriorScores: Record<string, number>,   // updated probabilities, same keys as mlScores
 *   details:         Record<string, object>,   // per-condition Bayesian trace
 * }
 */

const _rawBackendUrl = process.env.RAILWAY_API_URL ?? process.env.BACKEND_URL ?? 'http://localhost:8000';
const RAILWAY_URL = _rawBackendUrl.startsWith('http') ? _rawBackendUrl : `https://${_rawBackendUrl}`;

async function callRailway(body: object): Promise<Record<string, unknown>> {
  const res = await fetch(`${RAILWAY_URL}/bayesian/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await res.json() as Record<string, unknown>;

  if (!res.ok || data.error) {
    return { error: String(data.error ?? `Railway returned ${res.status}`) };
  }

  // Translate Python snake_case keys to camelCase expected by the frontend
  return {
    posteriorScores: data.posterior_scores ?? data.posteriorScores ?? {},
    details: data.details ?? {},
  };
}

export async function POST(req: NextRequest) {
  let mlScores: Record<string, number>;
  let confounderAnswers: Record<string, number>;
  let answersByCondition: Record<string, Record<string, string>>;
  let patientSex: string | undefined;
  let existingAnswers: Record<string, unknown>;
  let privacy: ServerPrivacyContext | null;

  try {
    const body = await req.json() as {
      mlScores?: unknown;
      confounderAnswers?: unknown;
      answersByCondition?: unknown;
      patientSex?: unknown;
      existingAnswers?: unknown;
      privacy?: unknown;
    };
    mlScores = (body.mlScores ?? {}) as Record<string, number>;
    confounderAnswers = (body.confounderAnswers ?? {}) as Record<string, number>;
    answersByCondition = (body.answersByCondition ?? {}) as Record<string, Record<string, string>>;
    patientSex = typeof body.patientSex === 'string' ? body.patientSex : undefined;
    existingAnswers = (body.existingAnswers ?? {}) as Record<string, unknown>;
    privacy = readOptionalPrivacyContext(body.privacy);
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body or consent payload' }, { status: 400 });
  }

  const result = await callRailway({
    mode: 'update',
    ml_scores: mlScores,
    confounder_answers: confounderAnswers,
    answers_by_condition: answersByCondition,
    patient_sex: patientSex,
    existing_answers: existingAnswers,
  });

  if (result.error) {
    writeLog('bayesian_update_error', {
      anonymousId: privacy?.anonymousId ?? null,
      mlScoreKeys: Object.keys(mlScores),
      error: result.error,
    });
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  if (privacy) {
    await persistHealthSession({
      privacy,
      sessionKind: 'bayesian_update',
      payload: {
        mlScores,
        confounderAnswers,
        answersByCondition,
        patientSex,
        existingAnswers,
        result,
      },
      profileSummary: {
        mlScoreKeys: Object.keys(mlScores),
        updatedConditionCount: Object.keys(answersByCondition).length,
      },
    });
  }

  writeLog('bayesian_update', {
    anonymousId: privacy?.anonymousId ?? null,
    mlScoreKeys: Object.keys(mlScores),
    updatedConditionCount: Object.keys(answersByCondition).length,
  });
  return NextResponse.json(result);
}
