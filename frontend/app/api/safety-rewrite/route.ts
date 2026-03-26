import { NextRequest, NextResponse } from 'next/server';
import { applyHardSafetyRules, validateDeepAnalyzeSchema } from '@/lib/medgemma-safety';
import { rewriteDeepAnalyzeTone } from '@/src/lib/server/deepAnalyzeSafety';

export async function POST(req: NextRequest) {
  const body = await req.json();
  const candidate = (body?.report ?? body) as Record<string, unknown>;
  const inputValidation = validateDeepAnalyzeSchema(candidate);
  if (!inputValidation.ok) {
    return NextResponse.json(
      { error: 'invalid_input_schema', detail: inputValidation.reason },
      { status: 400 },
    );
  }

  const rewritten = await rewriteDeepAnalyzeTone(inputValidation.data);
  const { data: safeData } = applyHardSafetyRules(rewritten);
  return NextResponse.json(safeData);
}
