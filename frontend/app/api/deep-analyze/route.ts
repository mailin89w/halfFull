import { NextRequest, NextResponse } from 'next/server';
import { formatAnswersV2 } from '@/src/lib/formatAnswers';
import { writeLog } from '@/src/lib/logger';
import { ML_THRESHOLD, selectTopConditions } from '@/src/lib/mlConfig';
import {
  buildAnsweredQuestionsText,
  buildUploadedLabsText,
} from '@/src/lib/assessmentPromptContext';
import {
  buildAllClearPrompt,
  buildMedGemmaGroundingPromptV6,
  buildGroqSynthesisPromptV6,
  MEDGEMMA_JSON_SYSTEM_V1,
} from '@/src/lib/prompts';
import {
  applyHardSafetyRules,
  validateMedGemmaGroundingSchema,
  type MedGemmaGroundingResult,
} from '@/lib/medgemma-safety';
import { synthesizeNarrativeWithGroqV6 } from '@/src/lib/server/deepAnalyzeSafety';
import { selectOneShotExample } from '@/src/lib/oneShotExamples';

export const maxDuration = 300; // Vercel max on Pro plan; covers Modal cold-start + inference

const _rawBackendUrl = process.env.RAILWAY_API_URL ?? process.env.BACKEND_URL ?? 'http://localhost:8000';
const RAILWAY_URL = _rawBackendUrl.startsWith('http') ? _rawBackendUrl : `https://${_rawBackendUrl}`;
const HF_MODEL = 'google/medgemma-1.5-4b-it';
const HF_API_URL = process.env.HF_ENDPOINT_URL
  ? `${process.env.HF_ENDPOINT_URL}/v1/chat/completions`
  : 'https://router.huggingface.co/v1/chat/completions';

/**
 * Attempts to parse potentially-truncated JSON from MedGemma.
 * Handles: incomplete strings, dangling commas, unclosed arrays/objects.
 */
function repairAndParseJson(raw: string): Record<string, unknown> | null {
  // First try straight parse
  try { return JSON.parse(raw) as Record<string, unknown>; } catch { /* fall through */ }

  // Build a bracket stack to find what needs closing
  let inString = false;
  let escaped = false;
  const stack: string[] = [];

  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (escaped) { escaped = false; continue; }
    if (ch === '\\' && inString) { escaped = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === '{') stack.push('}');
    else if (ch === '[') stack.push(']');
    else if ((ch === '}' || ch === ']') && stack.length > 0) stack.pop();
  }

  // Strip trailing comma / incomplete key-value, close any open string, close open structures
  let trimmed = raw.trimEnd();
  if (inString) trimmed += '"';                    // close dangling string
  trimmed = trimmed.replace(/,\s*$/, '');          // remove trailing comma
  const closing = stack.reverse().join('');

  try { return JSON.parse(trimmed + closing) as Record<string, unknown>; } catch { /* fall through */ }

  // Last resort: find the last valid } and try from the start to there
  for (let end = trimmed.length - 1; end > 1; end--) {
    if (trimmed[end] === '}') {
      try { return JSON.parse(trimmed.slice(0, end + 1)) as Record<string, unknown>; } catch { /* continue */ }
    }
  }

  return null;
}

export async function POST(req: NextRequest) {
  const hfToken = process.env.HF_API_TOKEN;
  if (!hfToken || hfToken === 'hf_your_token_here') {
    return NextResponse.json({ error: 'HF_API_TOKEN is not configured.' }, { status: 500 });
  }

  interface ClarificationQAPair { group: string; question: string; answer: string; }
  interface KnnSignal { lab: string; direction: string; neighbour_pct: number; lift: number | null; ref_lower: number | null; ref_upper: number | null; context: string | null; }
  interface KnnResult { lab_signals: KnnSignal[]; n_signals: number; k_neighbours: number; disabled?: boolean; }

  const body = await req.json();
  const answers: Record<string, unknown> = body.answers ?? {};
  const mlScores: Record<string, number> | undefined = body.mlScores;
  const clarificationQA: ClarificationQAPair[] | undefined = body.clarificationQA;
  const confirmedConditions: string[] = Array.isArray(body.confirmedConditions)
    ? body.confirmedConditions.map((value: unknown) => String(value))
    : [];
  const useKNN: boolean = body.useKNN === true;

  const symptomsText = formatAnswersV2(answers);
  const answeredQuestionsText = buildAnsweredQuestionsText(answers);
  const uploadedLabsText = buildUploadedLabsText(answers);
  const structuredAnswersJson = JSON.stringify(answers, null, 2);
  const fatigueSeverityRaw = answers['dpq040___feeling_tired_or_having_little_energy'];
  const fatigueSeverity = fatigueSeverityRaw === undefined ? null : Number(fatigueSeverityRaw);

  const topConditions = mlScores ? selectTopConditions(mlScores) : [];
  const flaggedConditions = topConditions
    .filter(([, p]) => p >= ML_THRESHOLD)
    .map(([c]) => c);

  const flaggedAreasText = topConditions.length > 0
    ? topConditions
      .map(([condition, prob]) => `- ${condition}: ${(prob * 100).toFixed(1)}%`)
      .join('\n')
    : '- None';

  const bayesianEvidenceText = clarificationQA && clarificationQA.length > 0
    ? clarificationQA
      .map((qa) => `- [${qa.group}] ${qa.question} -> ${qa.answer}`)
      .join('\n')
    : 'No Bayesian follow-up evidence provided.';

  const scoreSummaryJson = JSON.stringify({
    threshold: ML_THRESHOLD,
    topConditions,
    allScores: mlScores ?? {},
    filteredHighScoreConditions: flaggedConditions,
    confirmedConditions,
  }, null, 2);

  // [ADDED] Healthy user path: no scores or everything below 0.35
  const isAllClear =
    !mlScores || Object.values(mlScores).every((p) => p < 0.35);

  // ── KNN neighbour lab signals (optional, toggle via useKNN in request body) ──
  let knnResult: KnnResult | null = null;
  let knnLabText: string | null = null;

  if (useKNN && !isAllClear) {
    try {
      const knnRes = await fetch(`${RAILWAY_URL}/knn-score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(answers),
      });
      if (knnRes.ok) {
        knnResult = await knnRes.json() as KnnResult;
        const signals = knnResult.lab_signals ?? [];
        if (signals.length > 0) {
          const k = knnResult.k_neighbours ?? 50;
          knnLabText = [
            `NEAREST-NEIGHBOUR LAB SIGNALS (from ${k} people in our database with the most similar symptom profile):`,
            `These labs were disproportionately abnormal in patients most similar to this one. Use as additional supporting evidence for nextSteps and doctorKit — these are population-level patterns, not this patient's own results.`,
            ...signals.slice(0, 8).map((s) => {
              const ref = s.ref_lower != null && s.ref_upper != null
                ? ` [ref: ${s.ref_lower}–${s.ref_upper}]` : '';
              const lift = s.lift != null ? ` (${s.lift}x vs population)` : '';
              const ctx = s.context ? ` — ${s.context}` : '';
              return `- ${s.lab}: ${s.direction.toUpperCase()} in ${s.neighbour_pct}% of similar people${lift}${ref}${ctx}`;
            }),
          ].join('\n');
        }
      }
    } catch {
      // KNN is additive — silently skip if the Railway scorer is unavailable
    }
  }

  // ── V6 all-clear path: skip MedGemma entirely, synthesize directly via Groq ──
  if (isAllClear) {
    try {
      const allClearPrompt = buildAllClearPrompt({ symptomsText, answeredQuestionsText, uploadedLabsText });
      const allClearResult = await synthesizeNarrativeWithGroqV6(allClearPrompt);
      if (!allClearResult) {
        return NextResponse.json({ error: 'Groq synthesis unavailable for all-clear path' }, { status: 503 });
      }
      const { data: safeData, warnings } = applyHardSafetyRules(allClearResult);
      if (warnings.length > 0) writeLog('deep_analyze_safety_replacements', { answers, warnings });
      writeLog('deep_analyze', { answers, mlScores, allClear: true, result: safeData });
      return NextResponse.json(safeData);
    } catch (err) {
      writeLog('deep_analyze_error', { answers, mlScores, error: String(err) });
      return NextResponse.json({ error: String(err) }, { status: 500 });
    }
  }

  // ── V6 non-all-clear path: Call 1 MedGemma grounding → Call 2 Groq synthesis ─

  // Call 1: MedGemma clinical grounding (no PDF labs — structured Q&A only)
  const groundingPrompt = buildMedGemmaGroundingPromptV6({
    answeredQuestionsText,
    bayesianEvidenceText,
    scoreSummaryJson,
    knnLabText,
    prioritizedConditions: flaggedConditions,
    confirmedConditions,
  });

  let groundingResult: MedGemmaGroundingResult = {
    supportedSuspicions: [],
    declinedSuspicions: [],
    medicationFlags: [],
    recommendedSpecialties: [],
  };

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90_000);
    const hfResponse = await fetch(HF_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${hfToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: HF_MODEL,
        messages: [
          { role: 'system', content: MEDGEMMA_JSON_SYSTEM_V1 },
          { role: 'user', content: groundingPrompt },
        ],
        max_tokens: 800,
        temperature: 0.1,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    if (!hfResponse.ok) {
      const errText = await hfResponse.text();
      writeLog('medgemma_grounding_error', { answers, mlScores, status: hfResponse.status, errText });
      // Proceed with empty grounding — Groq synthesis still runs
    } else {
      const hfData = await hfResponse.json();
      const rawContent: string = hfData.choices?.[0]?.message?.content ?? '';

      // Step 5: log full raw MedGemma output before any processing
      writeLog('medgemma_grounding_raw', {
        answers,
        mlScores,
        flaggedConditions,
        confirmedConditions,
        groundingPrompt,
        rawOutput: rawContent,
      });

      const jsonMatch = rawContent.match(/\{[\s\S]*/);
      if (jsonMatch) {
        const parsed = repairAndParseJson(jsonMatch[0]);
        const validation = validateMedGemmaGroundingSchema(parsed);
        if (validation.ok) {
          groundingResult = validation.data;
        } else {
          writeLog('medgemma_grounding_schema_error', {
            answers, mlScores, reason: validation.reason, raw: rawContent,
          });
        }
      }
    }
  } catch (err) {
    writeLog('medgemma_grounding_error', { answers, mlScores, error: String(err) });
    // Continue with empty grounding — Groq synthesis still runs
  }

  // Call 2: Groq narrative synthesis (primary synthesis, not a patch)
  try {
    const synthesisPrompt = buildGroqSynthesisPromptV6({
      groundingResultJson: JSON.stringify(groundingResult, null, 2),
      fatigueSeverity,
      oneShot: selectOneShotExample(groundingResult),
    });

    const synthesisResult = await synthesizeNarrativeWithGroqV6(synthesisPrompt);
    if (!synthesisResult) {
      return NextResponse.json({ error: 'Groq synthesis unavailable' }, { status: 503 });
    }

    const { data: safeData, warnings: safetyWarnings } = applyHardSafetyRules(synthesisResult);
    if (safetyWarnings.length > 0) {
      writeLog('deep_analyze_safety_replacements', { answers, mlScores, warnings: safetyWarnings });
      for (const warning of safetyWarnings) console.warn(warning);
    }

    writeLog('deep_analyze', {
      answers,
      mlScores,
      clarificationQA,
      confirmedConditions,
      topConditions,
      fatigueSeverity,
      useKNN,
      knnSignals: knnResult,
      groundingResult,
      result: safeData,
    });

    return NextResponse.json({
      ...safeData,
      ...(knnResult ? { knnSignals: knnResult } : {}),
    });
  } catch (err) {
    writeLog('deep_analyze_error', { answers, mlScores, error: String(err) });
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
