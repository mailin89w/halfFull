import { randomBytes, scryptSync } from 'node:crypto';
import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import {
  buildHealthDataSummary,
  normalizeConsentGrantContext,
  persistHealthSession,
  recordConsentAcceptance,
} from '@/src/lib/server/privacy';

function getSupabaseAdmin() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

function hashPassword(password: string): string {
  const salt = randomBytes(16).toString('hex');
  const hash = scryptSync(password, salt, 64).toString('hex');
  return `${salt}:${hash}`;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as {
      login?: unknown;
      password?: unknown;
      privacy?: unknown;
      snapshot?: {
        answers?: Record<string, unknown>;
        mlScores?: Record<string, number>;
        confirmedConditions?: string[];
        deepResult?: Record<string, unknown> | null;
      };
    };

    const login = typeof body.login === 'string' ? body.login.trim() : '';
    const password = typeof body.password === 'string' ? body.password : '';

    if (login.length < 3) {
      return NextResponse.json({ error: 'Login must be at least 3 characters.' }, { status: 400 });
    }
    if (password.length < 8) {
      return NextResponse.json({ error: 'Password must be at least 8 characters.' }, { status: 400 });
    }

    const privacy = normalizeConsentGrantContext(body.privacy);
    await recordConsentAcceptance(privacy, {
      source: 'account_create',
      login,
    });

    const answers = body.snapshot?.answers ?? {};
    if (Object.keys(answers).length > 0) {
      await persistHealthSession({
        privacy,
        sessionKind: 'account_create',
        payload: {
          answers,
          mlScores: body.snapshot?.mlScores ?? {},
          confirmedConditions: body.snapshot?.confirmedConditions ?? [],
          deepResult: body.snapshot?.deepResult ?? null,
        },
        profileSummary: {
          ...buildHealthDataSummary(answers),
          confirmedConditions: body.snapshot?.confirmedConditions ?? [],
          scoreKeys: Object.keys(body.snapshot?.mlScores ?? {}),
          hasDeepResult: Boolean(body.snapshot?.deepResult),
          accountLogin: login,
        },
      });
    }

    const supabase = getSupabaseAdmin();
    if (!supabase) {
      return NextResponse.json({ error: 'Supabase is not configured.' }, { status: 500 });
    }

    const passwordHash = hashPassword(password);
    const { error } = await supabase
      .from('app_accounts')
      .insert({
        login,
        password_hash: passwordHash,
        anonymous_id: privacy.anonymousId,
      });

    if (error) {
      if (error.message.toLowerCase().includes('duplicate') || error.message.toLowerCase().includes('unique')) {
        return NextResponse.json({ error: 'That login is already taken.' }, { status: 409 });
      }
      throw error;
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Could not create account.' },
      { status: 400 }
    );
  }
}
