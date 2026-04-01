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
  buildGroqSynthesisFallbackPromptV7,
  buildGroqSynthesisPromptV7,
  MEDGEMMA_JSON_SYSTEM_V1,
} from '@/src/lib/prompts';
import {
  computeConfidence,
  computeUrgency,
  extractBiomarkerSnapshot,
  type ConfidenceTier,
  type UrgencyLevel,
} from '@/src/lib/clinicalSignals';
import {
  applyHardSafetyRules,
  validateMedGemmaGroundingSchema,
  type DeclinedSuspicion,
  type MedGemmaGroundingResult,
} from '@/lib/medgemma-safety';
import { rewriteDeepAnalyzeTone, synthesizeNarrativeWithGroqV6 } from '@/src/lib/server/deepAnalyzeSafety';
import { selectOneShotExample } from '@/src/lib/oneShotExamples';
import {
  buildHealthDataSummary,
  persistHealthSession,
  readOptionalPrivacyContext,
  type ServerPrivacyContext,
} from '@/src/lib/server/privacy';
import { ENABLE_KNN_LAYER } from '@/src/lib/featureFlags';

export const maxDuration = 300; // Vercel max on Pro plan; covers Modal cold-start + inference

const _rawBackendUrl = process.env.RAILWAY_API_URL ?? process.env.BACKEND_URL ?? 'http://localhost:8000';
const RAILWAY_URL = _rawBackendUrl.startsWith('http') ? _rawBackendUrl : `https://${_rawBackendUrl}`;
const HF_MODEL = 'google/medgemma-1.5-4b-it';
const HF_API_URL = process.env.HF_ENDPOINT_URL
  ? `${process.env.HF_ENDPOINT_URL}/v1/chat/completions`
  : 'https://router.huggingface.co/v1/chat/completions';
const EVAL_MODE_SECRET = process.env.EVAL_MODE_SECRET;
const EVAL_MODE_HEADER = 'x-eval-mode-secret';

type PromptCalibrationSignal = {
  conditionId: string;
  rawMlScore: number;
  effectiveScore: number;
  confidenceTier: ConfidenceTier;
  urgencyLevel: UrgencyLevel;
  clusterAgreement: number;
  scoreSuppressed: boolean;
  confidenceSummary: string;
  urgencySummary: string;
};

function buildRiskCalibrationText(signals: PromptCalibrationSignal[]): string {
  if (signals.length === 0) {
    return 'No elevated conditions reached the calibration layer.';
  }

  return signals
    .map((signal) => {
      const suppressionText = signal.scoreSuppressed
        ? `score_suppressed: yes (${signal.rawMlScore.toFixed(2)} -> ${signal.effectiveScore.toFixed(2)})`
        : 'score_suppressed: no';

      return [
        `- ${signal.conditionId}: raw_ml=${signal.rawMlScore.toFixed(2)} | effective_score=${signal.effectiveScore.toFixed(2)} | confidence=${signal.confidenceTier} | urgency=${signal.urgencyLevel} | cluster_agreement=${Math.round(signal.clusterAgreement * 100)}% | ${suppressionText}`,
        `  Confidence note: ${signal.confidenceSummary}`,
        `  Urgency note: ${signal.urgencySummary}`,
      ].join('\n');
    })
    .join('\n');
}

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

function ensureCandidateCoverage(
  flaggedConditions: string[],
  result: {
    insights: Array<{ diagnosisId: string }>;
    declinedSuspicions?: DeclinedSuspicion[];
  },
): DeclinedSuspicion[] | undefined {
  const existingIds = new Set([
    ...result.insights.map((item) => item.diagnosisId),
    ...(result.declinedSuspicions ?? []).map((item) => item.diagnosisId),
  ]);

  const appended = flaggedConditions
    .filter((diagnosisId) => !existingIds.has(diagnosisId))
    .map((diagnosisId) => ({
      diagnosisId,
      reason: 'This signal was reviewed but was not strong enough to prioritise after the full evidence check.',
    }));

  if ((result.declinedSuspicions?.length ?? 0) === 0 && appended.length === 0) {
    return result.declinedSuspicions;
  }

  return [...(result.declinedSuspicions ?? []), ...appended];
}

function toTitleCaseSummaryPoint(text: string): string {
  const trimmed = text.trim().replace(/[.;:,]+$/, '');
  if (!trimmed) return '';
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

const SUMMARY_POINT_FORBIDDEN = [
  /\bthyroid\b/i,
  /\banemi[ao]?\b/i,
  /\bprediabet/i,
  /\bglucose\b/i,
  /\bhepatitis\b/i,
  /\bliver\b/i,
  /\bkidney\b/i,
  /\biron deficiency\b/i,
  /\biron\b/i,
  /\bsleep disorder\b/i,
  /\belectrolyte/i,
  /\binflammation\b/i,
  /\bcondition\b/i,
  /\bdiagnos/i,
  /\bsyndrome\b/i,
  /\bdoctor\b/i,
  /\bspecialist\b/i,
  /\btest\b/i,
  /\blab\b/i,
  /\bmarker\b/i,
  /\bfollow-?up\b/i,
  /\brule out\b/i,
  /\bworth discussing\b/i,
  /\bmay be a concern\b/i,
];

function normalizeStructuredSummaryPoints(
  existingPoints: string[] | undefined,
  candidatePoints: string[],
): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];

  const tryAdd = (value: string) => {
    const cleaned = toTitleCaseSummaryPoint(value);
    if (!cleaned) return;
    if (SUMMARY_POINT_FORBIDDEN.some((pattern) => pattern.test(cleaned))) return;
    const wordCount = cleaned.split(/\s+/).filter(Boolean).length;
    if (wordCount < 2 || wordCount > 10) return;
    const dedupeKey = cleaned.toLowerCase();
    if (seen.has(dedupeKey)) return;
    seen.add(dedupeKey);
    normalized.push(cleaned);
  };

  for (const value of candidatePoints) {
    if (normalized.length >= 3) break;
    tryAdd(value);
  }
  for (const value of existingPoints ?? []) {
    if (normalized.length >= 3) break;
    tryAdd(value);
  }

  return normalized.slice(0, 3);
}

function annotateDeepAnalyzeResponse(
  response: NextResponse,
  metadata: {
    groundingSource: string;
    synthesisSource: string;
    synthesisModel?: string;
    synthesisStatus?: number;
    synthesisErrorSnippet?: string;
    rewriteSource?: string;
    rewriteModel?: string;
    rewriteStatus?: number;
    rewriteErrorSnippet?: string;
    hardSafetyCount: number;
  },
): NextResponse {
  response.headers.set('x-deep-analyze-grounding-source', metadata.groundingSource);
  response.headers.set('x-deep-analyze-synthesis-source', metadata.synthesisSource);
  response.headers.set('x-deep-analyze-hard-safety-count', String(metadata.hardSafetyCount));
  response.headers.set(
    'x-deep-analyze-hard-safety-applied',
    metadata.hardSafetyCount > 0 ? 'true' : 'false',
  );
  if (metadata.synthesisModel) {
    response.headers.set('x-deep-analyze-synthesis-model', metadata.synthesisModel);
  }
  if (metadata.synthesisStatus !== undefined) {
    response.headers.set('x-deep-analyze-synthesis-status', String(metadata.synthesisStatus));
  }
  if (metadata.synthesisErrorSnippet) {
    response.headers.set(
      'x-deep-analyze-synthesis-error-snippet',
      encodeURIComponent(metadata.synthesisErrorSnippet),
    );
  }
  if (metadata.rewriteSource) {
    response.headers.set('x-deep-analyze-rewrite-source', metadata.rewriteSource);
  }
  if (metadata.rewriteModel) {
    response.headers.set('x-deep-analyze-rewrite-model', metadata.rewriteModel);
  }
  if (metadata.rewriteStatus !== undefined) {
    response.headers.set('x-deep-analyze-rewrite-status', String(metadata.rewriteStatus));
  }
  if (metadata.rewriteErrorSnippet) {
    response.headers.set(
      'x-deep-analyze-rewrite-error-snippet',
      encodeURIComponent(metadata.rewriteErrorSnippet),
    );
  }
  return response;
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
  const rawMlScores: Record<string, number> | undefined = body.rawMlScores;
  const evalMode: 'default' | 'medgemma_only' =
    body.evalMode === 'medgemma_only' ? 'medgemma_only' : 'default';
  const evalHeaderSecret = req.headers.get(EVAL_MODE_HEADER);

  if (evalMode === 'medgemma_only') {
    if (!EVAL_MODE_SECRET) {
      return NextResponse.json(
        { error: 'medgemma_only eval mode is disabled on this deployment.' },
        { status: 403 },
      );
    }

    if (evalHeaderSecret !== EVAL_MODE_SECRET) {
      return NextResponse.json(
        { error: 'Invalid eval mode secret.' },
        { status: 403 },
      );
    }
  }

  const evalCandidateConditions: string[] = Array.isArray(body.evalCandidateConditions)
    ? body.evalCandidateConditions.map((value: unknown) => String(value)).filter(Boolean)
    : [];
  let privacy: ServerPrivacyContext | null;

  try {
    privacy = readOptionalPrivacyContext(body.privacy);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Invalid consent payload.' },
      { status: 400 }
    );
  }
  const clarificationQA: ClarificationQAPair[] | undefined = body.clarificationQA;
  const confirmedConditions: string[] = Array.isArray(body.confirmedConditions)
    ? body.confirmedConditions.map((value: unknown) => String(value))
    : [];
  const useKNN: boolean = ENABLE_KNN_LAYER && body.useKNN === true;

  const symptomsText = formatAnswersV2(answers);
  const answeredQuestionsText = buildAnsweredQuestionsText(answers);
  const uploadedLabsText = buildUploadedLabsText(answers);
  const biomarkers = extractBiomarkerSnapshot(answers);
  const fatigueSeverityRaw = answers['dpq040___feeling_tired_or_having_little_energy'];
  const fatigueSeverity = fatigueSeverityRaw === undefined ? null : Number(fatigueSeverityRaw);

  const topConditions = mlScores ? selectTopConditions(mlScores) : [];
  const flaggedConditions = evalMode === 'medgemma_only'
    ? evalCandidateConditions
    : topConditions
      .filter(([, p]) => p >= ML_THRESHOLD)
      .map(([c]) => c);

  const bayesianEvidenceText = clarificationQA && clarificationQA.length > 0
    ? clarificationQA
      .map((qa) => `- [${qa.group}] ${qa.question} -> ${qa.answer}`)
      .join('\n')
    : 'No Bayesian follow-up evidence provided.';

  const scoreSummaryJson = evalMode === 'medgemma_only'
    ? JSON.stringify({
        mode: 'medgemma_only',
        note: 'ML scores intentionally withheld for quiz-only evaluation. Review the candidate conditions using questionnaire evidence only.',
        candidateConditions: flaggedConditions,
        confirmedConditions,
      }, null, 2)
    : JSON.stringify({
        threshold: ML_THRESHOLD,
        topConditions,
        allScores: mlScores ?? {},
        filteredHighScoreConditions: flaggedConditions,
        confirmedConditions,
      }, null, 2);

  // [ADDED] Healthy user path: no scores or everything below 0.35
  const isAllClear =
    evalMode === 'medgemma_only'
      ? false
      : (!mlScores || Object.values(mlScores).every((p) => p < 0.35));

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

  const promptCalibrationSignals: PromptCalibrationSignal[] = evalMode === 'medgemma_only'
    ? []
    : topConditions.map(([conditionId]) => {
    const rawMlScore = rawMlScores?.[conditionId] ?? mlScores?.[conditionId] ?? 0;
    const effectiveScore = mlScores?.[conditionId] ?? rawMlScore;
    const confidence = computeConfidence({
      conditionId,
      mlScore: rawMlScore,
      posteriorScore: effectiveScore,
      labSignals: knnResult?.lab_signals,
    });
    const urgency = computeUrgency({
      conditionId,
      posteriorScore: effectiveScore,
      biomarkers,
    });

    return {
      conditionId,
      rawMlScore,
      effectiveScore,
      confidenceTier: confidence.tier,
      urgencyLevel: urgency.level,
      clusterAgreement: confidence.clusterAgreement,
      scoreSuppressed: effectiveScore + 0.05 < rawMlScore,
      confidenceSummary: confidence.summary,
      urgencySummary: urgency.reasons[0] ?? urgency.cta,
    };
    });
  const riskCalibrationText = buildRiskCalibrationText(promptCalibrationSignals);
  const overallUrgency: UrgencyLevel =
    promptCalibrationSignals.some((signal) => signal.urgencyLevel === 'urgent')
      ? 'urgent'
      : promptCalibrationSignals.some((signal) => signal.urgencyLevel === 'soon')
        ? 'soon'
        : 'routine';

  // ── V6 all-clear path: skip MedGemma entirely, synthesize directly via Groq ──
  if (isAllClear) {
    try {
      const allClearPrompt = buildAllClearPrompt({ symptomsText, answeredQuestionsText, uploadedLabsText });
      const allClearResult = await synthesizeNarrativeWithGroqV6(allClearPrompt);
      if (!allClearResult.data) {
        return annotateDeepAnalyzeResponse(
          NextResponse.json({ error: 'LLM synthesis unavailable for all-clear path' }, { status: 503 }),
          {
            groundingSource: 'all_clear_skip_medgemma',
            synthesisSource: allClearResult.synthesisSource,
            synthesisModel: allClearResult.model,
            synthesisStatus: allClearResult.status,
            synthesisErrorSnippet: allClearResult.errorSnippet,
            hardSafetyCount: 0,
          },
        );
      }
      const normalizedAllClear = {
        ...allClearResult.data,
        summaryPoints: normalizeStructuredSummaryPoints(allClearResult.data.summaryPoints, []),
      };
      const rewriteResult = await rewriteDeepAnalyzeTone(normalizedAllClear);
      const { data: safeData, warnings } = applyHardSafetyRules(rewriteResult.data);
      if (warnings.length > 0) {
        await writeLog('deep_analyze_safety_replacements', {
          anonymousId: privacy?.anonymousId ?? null,
          warnings,
        });
      }

      if (privacy) {
        await persistHealthSession({
          privacy,
          sessionKind: 'deep_analyze_all_clear',
          payload: {
            answers,
            mlScores: mlScores ?? {},
            result: safeData,
            warnings,
          },
          profileSummary: {
            ...buildHealthDataSummary(answers),
            allClear: true,
          },
        });
      }

      await writeLog('deep_analyze', {
        anonymousId: privacy?.anonymousId ?? null,
        answers,
        mlScores: mlScores ?? {},
        rawMlScores: rawMlScores ?? {},
        clarificationQA: clarificationQA ?? [],
        confirmedConditions,
        fatigueSeverity,
        allClear: true,
        result: safeData,
      });
      return annotateDeepAnalyzeResponse(
        NextResponse.json(safeData),
        {
          groundingSource: 'all_clear_skip_medgemma',
          synthesisSource: allClearResult.synthesisSource,
          synthesisModel: allClearResult.model,
          synthesisStatus: allClearResult.status,
          synthesisErrorSnippet: allClearResult.errorSnippet,
          rewriteSource: rewriteResult.rewriteSource,
          rewriteModel: rewriteResult.model,
          rewriteStatus: rewriteResult.status,
          rewriteErrorSnippet: rewriteResult.errorSnippet,
          hardSafetyCount: warnings.length,
        },
      );
    } catch (err) {
      await writeLog('deep_analyze_error', {
        anonymousId: privacy?.anonymousId ?? null,
        answers,
        mlScores: mlScores ?? {},
        error: String(err),
      });
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
    riskCalibrationText: evalMode === 'medgemma_only' ? null : riskCalibrationText,
    candidateSourceLabel: evalMode === 'medgemma_only'
      ? 'Review these candidate conditions for this quiz-only eval arm. ML scores are intentionally withheld:'
      : undefined,
  });

  let groundingResult: MedGemmaGroundingResult = {
    supportedSuspicions: [],
    declinedSuspicions: [],
    medicationFlags: [],
    recommendedSpecialties: [],
  };
  let groundingSource =
    'fallback_empty_grounding' as
      | 'live_medgemma_success'
      | 'fallback_medgemma_http_error'
      | 'fallback_medgemma_schema_error'
      | 'fallback_medgemma_parse_failed'
      | 'fallback_medgemma_exception'
      | 'fallback_empty_grounding';

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 150_000);
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
      await writeLog('medgemma_grounding_error', {
        anonymousId: privacy?.anonymousId ?? null,
        status: hfResponse.status,
        errText,
        answers,
        flaggedConditions,
      });
      groundingSource = 'fallback_medgemma_http_error';
      // Proceed with empty grounding — Groq synthesis still runs
    } else {
      const hfData = await hfResponse.json();
      const rawContent: string = hfData.choices?.[0]?.message?.content ?? '';

      // Step 5: log full raw MedGemma output before any processing
      await writeLog('medgemma_grounding_raw', {
        anonymousId: privacy?.anonymousId ?? null,
        answers,
        mlScores: mlScores ?? {},
        rawMlScores: rawMlScores ?? {},
        flaggedConditions,
        confirmedConditions,
        groundingPrompt,
        rawOutput: rawContent,
      });

      const jsonMatch = rawContent.match(/\{[\s\S]*/);
      if (jsonMatch) {
        const parsed = repairAndParseJson(jsonMatch[0]);
        if (!parsed) {
          groundingSource = 'fallback_medgemma_parse_failed';
        } else {
          const validation = validateMedGemmaGroundingSchema(parsed);
          if (validation.ok) {
            groundingSource = 'live_medgemma_success';
            groundingResult = validation.data;
          } else {
            groundingSource = 'fallback_medgemma_schema_error';
            await writeLog('medgemma_grounding_schema_error', {
              anonymousId: privacy?.anonymousId ?? null,
              reason: validation.reason,
              raw: rawContent,
            });
          }
        }
      } else {
        groundingSource = 'fallback_medgemma_parse_failed';
      }
    }
  } catch (err) {
    await writeLog('medgemma_grounding_error', {
      anonymousId: privacy?.anonymousId ?? null,
      answers,
      mlScores: mlScores ?? {},
      error: String(err),
    });
    groundingSource = 'fallback_medgemma_exception';
    // Continue with empty grounding — Groq synthesis still runs
  }

  // Derive top Bayesian gain conditions from clarification QA
  const bayesianGainMap: Record<string, number> = {};
  for (const qa of (clarificationQA ?? [])) {
    const answerLower = (qa.answer ?? '').toLowerCase();
    const isConfirming = ['yes', 'often', 'always', 'severe', 'daily', 'frequent', 'regularly', 'every night', 'constantly'].some(
      (w) => answerLower.includes(w)
    );
    if (isConfirming) {
      bayesianGainMap[qa.group] = (bayesianGainMap[qa.group] ?? 0) + 1;
    }
  }
  // Ordered condition IDs by Bayesian confirming signal count
  const topBayesianConditionIds = Object.entries(bayesianGainMap)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)
    .map(([group]) => group);
  const topBayesianConditions = topBayesianConditionIds.map((id, i) =>
    `${id} (${bayesianGainMap[id]} confirming signal${bayesianGainMap[id] > 1 ? 's' : ''} from Bayesian follow-up)`.concat(i === 0 ? ' ← highest gain' : '')
  );

  // Call 2: Groq narrative synthesis V7
  try {
    const synthesisPrompt = buildGroqSynthesisPromptV7({
      groundingResultJson: JSON.stringify(groundingResult, null, 2),
      fatigueSeverity,
      riskCalibrationText,
      overallUrgency,
      oneShot: selectOneShotExample(groundingResult),
      topBayesianConditions,
    });
    const fallbackSynthesisPrompt = buildGroqSynthesisFallbackPromptV7({
      groundingResultJson: JSON.stringify(groundingResult, null, 2),
      overallUrgency,
    });

    const synthesisResult = await synthesizeNarrativeWithGroqV6({
      primaryPrompt: synthesisPrompt,
      fallbackPrompt: fallbackSynthesisPrompt,
    });
    if (!synthesisResult.data) {
      return annotateDeepAnalyzeResponse(
        NextResponse.json({ error: 'LLM synthesis unavailable' }, { status: 503 }),
        {
          groundingSource,
          synthesisSource: synthesisResult.synthesisSource,
          synthesisModel: synthesisResult.model,
          synthesisStatus: synthesisResult.status,
          synthesisErrorSnippet: synthesisResult.errorSnippet,
          hardSafetyCount: 0,
        },
      );
    }

    // ── Build deterministic personalizedSummary from top Bayesian confirming questions ──
    const SYMPTOM_BLACKLIST = [
      /\bfatigu/i, /\btired/i, /\btiredness/i, /\bexhaust/i, /\benergy\b/i,
      /\beducation/i, /\bincome/i, /\bbmi\b/i,
      /\bmedication/i, /\bsupplement/i, /\bvitamin\b/i,
      /\bfamily history/i, /\brelative\b/i,
      /several days/i, /over the past/i, /\bweeks?\b.*ago/i,
      /how (often|many|much|long)/i,
    ];
    const isSymptomBlacklisted = (text: string) => SYMPTOM_BLACKLIST.some((r) => r.test(text));

    function extractSymptomFromQuestion(question: string): string | null {
      const stripped = question
        .replace(/^do you (experience|have|feel|notice|get|suffer from|tend to get)\s+/i, '')
        .replace(/^have you (been experiencing|been having|noticed|had)\s+/i, '')
        .replace(/^are you (experiencing|having|suffering from)\s+/i, '')
        .replace(/^does (your\s+\w+\s+)?(feel|seem|appear|become)\s+/i, '')
        .replace(/^is your\s+\w+\s+/i, '')
        .replace(/\?$/, '')
        .trim();
      if (!stripped || isSymptomBlacklisted(stripped) || stripped.length < 3 || stripped.length > 70) return null;
      return stripped.charAt(0).toLowerCase() + stripped.slice(1);
    }

    const topSymptoms: string[] = [];

    // Primary: confirming Bayesian QA questions, sorted by Bayesian gain (highest first)
    const confirmingQA = (clarificationQA ?? []).filter((qa) => {
      const al = (qa.answer ?? '').toLowerCase();
      return ['yes', 'often', 'always', 'severe', 'daily', 'frequent', 'regularly', 'every night', 'constantly'].some(
        (w) => al.includes(w)
      );
    });
    const sortedQA = [...confirmingQA].sort(
      (a, b) => (bayesianGainMap[b.group] ?? 0) - (bayesianGainMap[a.group] ?? 0)
    );
    for (const qa of sortedQA) {
      if (topSymptoms.length >= 3) break;
      const sym = extractSymptomFromQuestion(qa.question);
      if (sym && !topSymptoms.includes(sym)) topSymptoms.push(sym);
    }

    // Secondary: keySymptoms from MedGemma grounding (with blacklist), ordered by Bayesian rank
    if (topSymptoms.length < 3 && groundingResult) {
      const orderedCondIds = [
        ...topBayesianConditionIds,
        ...groundingResult.supportedSuspicions.map((s) => s.diagnosisId),
      ];
      const seen = new Set<string>();
      for (const condId of orderedCondIds) {
        if (topSymptoms.length >= 3) break;
        if (seen.has(condId)) continue;
        seen.add(condId);
        const susp = groundingResult.supportedSuspicions.find((s) => s.diagnosisId === condId);
        for (const sym of (susp?.keySymptoms ?? [])) {
          if (topSymptoms.length >= 3) break;
          if (!isSymptomBlacklisted(sym) && sym.length < 70) {
            const normalized = sym.charAt(0).toLowerCase() + sym.slice(1);
            if (!topSymptoms.includes(normalized)) topSymptoms.push(normalized);
          }
        }
      }
    }

    let personalizedSummary = synthesisResult.data.personalizedSummary;
    if (topSymptoms.length >= 2) {
      const phrase =
        topSymptoms.length === 2
          ? `${topSymptoms[0]} and ${topSymptoms[1]}`
          : `${topSymptoms[0]}, ${topSymptoms[1]}, and ${topSymptoms[2]}`;
      personalizedSummary = `From what you shared, your fatigue is connected to the ${phrase}. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.`;
    }
    // If < 2 valid symptoms found, keep Groq's synthesised version unchanged

    const summaryPointCandidates = [
      ...topSymptoms,
      ...groundingResult.supportedSuspicions.flatMap((s) => s.keySymptoms ?? []),
      ...groundingResult.recommendedSpecialties.flatMap((s) => s.symptomsToRaise ?? []),
    ];

    const coveredResult = {
      ...synthesisResult.data,
      summaryPoints: normalizeStructuredSummaryPoints(
        synthesisResult.data.summaryPoints,
        summaryPointCandidates,
      ),
      personalizedSummary,
      declinedSuspicions: ensureCandidateCoverage(flaggedConditions, synthesisResult.data),
    };

    const rewriteResult = await rewriteDeepAnalyzeTone(coveredResult);
    const allowedDiagnosisIds = Array.from(new Set([
      ...topConditions.map(([conditionId]) => conditionId),
      ...confirmedConditions,
    ]));

    const { data: safeData, warnings: safetyWarnings } = applyHardSafetyRules(
      rewriteResult.data,
      { allowedDiagnosisIds },
    );
    if (safetyWarnings.length > 0) {
      await writeLog('deep_analyze_safety_replacements', {
        anonymousId: privacy?.anonymousId ?? null,
        warnings: safetyWarnings,
      });
      for (const warning of safetyWarnings) console.warn(warning);
    }

    if (privacy) {
      await persistHealthSession({
        privacy,
        sessionKind: 'deep_analyze',
        payload: {
          answers,
          mlScores: mlScores ?? {},
          clarificationQA: clarificationQA ?? [],
          confirmedConditions,
          topConditions,
          fatigueSeverity,
          useKNN,
          knnSignals: knnResult,
          promptCalibrationSignals,
          groundingResult,
          result: safeData,
        },
        profileSummary: {
          ...buildHealthDataSummary(answers),
          topConditionIds: topConditions.map(([condition]) => condition),
          confirmedConditions,
        },
      });
    }

    await writeLog('deep_analyze', {
      anonymousId: privacy?.anonymousId ?? null,
      answers,
      mlScores: mlScores ?? {},
      rawMlScores: rawMlScores ?? {},
      clarificationQA: clarificationQA ?? [],
      confirmedConditions,
      topConditions,
      fatigueSeverity,
      useKNN,
      knnSignals: knnResult,
      groundingResult,
      result: safeData,
      overallUrgency,
    });

    return annotateDeepAnalyzeResponse(
      NextResponse.json({
        ...safeData,
        ...(knnResult ? { knnSignals: knnResult } : {}),
      }),
      {
        groundingSource,
        synthesisSource: synthesisResult.synthesisSource,
        synthesisModel: synthesisResult.model,
        synthesisStatus: synthesisResult.status,
        synthesisErrorSnippet: synthesisResult.errorSnippet,
        rewriteSource: rewriteResult.rewriteSource,
        rewriteModel: rewriteResult.model,
        rewriteStatus: rewriteResult.status,
        rewriteErrorSnippet: rewriteResult.errorSnippet,
        hardSafetyCount: safetyWarnings.length,
      },
    );
  } catch (err) {
    await writeLog('deep_analyze_error', {
      anonymousId: privacy?.anonymousId ?? null,
      answers,
      mlScores: mlScores ?? {},
      rawMlScores: rawMlScores ?? {},
      clarificationQA: clarificationQA ?? [],
      error: String(err),
    });
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
