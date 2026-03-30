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
  const { data: safeData, warnings } = applyHardSafetyRules(rewritten.data);
  const response = NextResponse.json(safeData);
  response.headers.set('x-safety-rewrite-source', rewritten.rewriteSource);
  response.headers.set('x-safety-hard-rules-applied', warnings.length > 0 ? 'true' : 'false');
  response.headers.set('x-safety-hard-rule-count', String(warnings.length));
  if (rewritten.model) {
    response.headers.set('x-safety-rewrite-model', rewritten.model);
  }
  if (rewritten.status !== undefined) {
    response.headers.set('x-safety-rewrite-status', String(rewritten.status));
    response.headers.set('x-safety-groq-status', String(rewritten.status));
  }
  if (rewritten.errorSnippet) {
    response.headers.set('x-safety-rewrite-error-snippet', encodeURIComponent(rewritten.errorSnippet));
    response.headers.set('x-safety-groq-error-snippet', encodeURIComponent(rewritten.errorSnippet));
  }
  return response;
}
