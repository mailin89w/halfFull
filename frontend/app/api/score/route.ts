import { NextRequest, NextResponse } from 'next/server';
import { writeLog } from '@/src/lib/logger';
import {
  buildHealthDataSummary,
  persistHealthSession,
  readOptionalPrivacyContext,
  type ServerPrivacyContext,
} from '@/src/lib/server/privacy';

/**
 * POST /api/score
 *
 * Accepts a flat answers dict keyed by NHANES field_ids (values are
 * string-encoded NHANES codes, e.g. {"gender": "2", "age_years": "45"}).
 *
 * Proxies to Railway backend, returns:
 *   { scores: { anemia: 0.31, thyroid: 0.55, ... } }
 *
 * Errors return { error: string } with an appropriate status code.
 */

const _rawBackendUrl = process.env.RAILWAY_API_URL ?? process.env.BACKEND_URL ?? 'http://localhost:8000';
const RAILWAY_URL = _rawBackendUrl.startsWith('http') ? _rawBackendUrl : `https://${_rawBackendUrl}`;

async function callRailway(answers: Record<string, unknown>): Promise<{ scores?: Record<string, number>; confirmed?: string[]; error?: string }> {
  const res = await fetch(`${RAILWAY_URL}/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answers),
  });

  const data = await res.json() as Record<string, unknown>;

  if (!res.ok || data.error) {
    return { error: String(data.error ?? `Railway returned ${res.status}`) };
  }

  // Separate the `confirmed` list from model probability scores
  const { confirmed, ...scoreData } = data as { confirmed?: string[] } & Record<string, unknown>;
  return { scores: scoreData as Record<string, number>, confirmed: confirmed ?? [] };
}

export async function POST(req: NextRequest) {
  let answers: Record<string, unknown>;
  let privacy: ServerPrivacyContext | null;

  try {
    const body = await req.json() as { answers?: unknown; privacy?: unknown };
    answers = (body.answers ?? {}) as Record<string, unknown>;
    privacy = readOptionalPrivacyContext(body.privacy);
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body or consent payload' }, { status: 400 });
  }

  const result = await callRailway(answers);

  if (result.error) {
    await writeLog('score_error', {
      anonymousId: privacy?.anonymousId ?? null,
      answers,
      error: result.error,
    });
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  if (privacy) {
    await persistHealthSession({
      privacy,
      sessionKind: 'score',
      payload: {
        answers,
        scores: result.scores ?? {},
        confirmed: result.confirmed ?? [],
      },
      profileSummary: {
        ...buildHealthDataSummary(answers),
        confirmedConditions: result.confirmed ?? [],
        scoreKeys: Object.keys(result.scores ?? {}),
      },
    });
  }

  await writeLog('score', {
    anonymousId: privacy?.anonymousId ?? null,
    answers,
    scores: result.scores ?? {},
    confirmed: result.confirmed ?? [],
  });
  return NextResponse.json({ scores: result.scores, confirmed: result.confirmed ?? [] });
}
