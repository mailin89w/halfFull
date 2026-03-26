import { NextRequest, NextResponse } from 'next/server';
import {
  buildHealthDataSummary,
  persistHealthSession,
  recordConsentAcceptance,
  validatePrivacyContext,
} from '@/src/lib/server/privacy';
import { writeLog } from '@/src/lib/logger';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as {
      privacy?: unknown;
      source?: string;
      snapshot?: {
        answers?: Record<string, unknown>;
        mlScores?: Record<string, number>;
        confirmedConditions?: string[];
        deepResult?: Record<string, unknown> | null;
      };
    };

    const privacy = validatePrivacyContext(body.privacy);
    await recordConsentAcceptance(privacy, {
      source: body.source ?? 'consent_page',
    });

    const answers = body.snapshot?.answers ?? {};
    if (Object.keys(answers).length > 0) {
      await persistHealthSession({
        privacy,
        sessionKind: 'profile_save',
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
        },
      });
    }

    writeLog('privacy_consent_granted', {
      anonymousId: privacy.anonymousId,
      consentVersion: privacy.consentVersion,
      source: body.source ?? 'consent_page',
      savedProfile: Object.keys(answers).length > 0,
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    writeLog('privacy_consent_error', {
      error: String(error),
    });
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Invalid consent payload' },
      { status: 400 }
    );
  }
}
