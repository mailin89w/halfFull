import { NextRequest, NextResponse } from 'next/server';
import { recordConsentExit, validatePrivacyContext } from '@/src/lib/server/privacy';
import { writeLog } from '@/src/lib/logger';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { privacy?: unknown };
    const privacy = validatePrivacyContext(body.privacy);

    await recordConsentExit(privacy);
    await writeLog('privacy_exit', {
      anonymousId: privacy.anonymousId,
      consentVersion: privacy.consentVersion,
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    await writeLog('privacy_exit_error', {
      error: String(error),
    });
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Invalid exit payload' },
      { status: 400 }
    );
  }
}
