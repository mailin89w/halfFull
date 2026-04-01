import { validateDeepAnalyzeSchema, type DeepAnalyzeResult } from '@/lib/medgemma-safety';

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions';
const GROQ_MODEL = 'llama-3.1-8b-instant';
// V7: primary synthesis model; fallback chain: groq-70b → groq-8b → openai-4o-mini
const GROQ_SYNTHESIS_MODEL = 'llama-3.3-70b-versatile';
const GROQ_SYNTHESIS_FALLBACK_MODEL = 'llama-3.1-8b-instant';
const OPENAI_SYNTHESIS_MODEL = 'gpt-5-mini';
const GROQ_MAX_429_RETRIES = 3;
const GROQ_BACKOFF_BASE_MS = 1000;

const SAFETY_SYSTEM_PROMPT = `You are a medical communication safety filter. Rewrite only the user-facing narrative fields so they stay warm, non-diagnostic, and appropriately uncertain.

Rules:
- Never say a diagnosis is confirmed unless the input explicitly says it is already medically confirmed
- Use possibility framing such as "may suggest", "could indicate", and "worth discussing with your doctor"
- Remove alarmist wording, but do not soften or delete urgent safety guidance when red-flag symptoms are present
- Remove dismissive reassurance such as "nothing serious", "you are fine", "safe to ignore", "safe to stay home", "no need to see a doctor", "just stress", "watch and see", "likely benign", "not worrisome", or long delays like "wait a few weeks" / "wait a month" / "wait a year"
- If the content mentions red-flag symptoms such as chest pain, breathlessness, black stools, jaundice, confusion, fainting, near-fainting, or palpitations, the output must keep or add urgent review language such as "urgent", "prompt", "same day", "today", "immediate", or "emergency"
- Keep the same overall meaning, specificity, and structure
- Rewrite these fields when present: personalizedSummary, summaryPoints[], insights[].personalNote, declinedSuspicions[].reason, recoveryOutlook, nextSteps, doctorKitSummary, doctorKitQuestions[], doctorKitArguments[], recommendedDoctors[].reason, recommendedDoctors[].symptomsToDiscuss[], doctorKits[].openingSummary, doctorKits[].discussionPoints[], doctorKits[].whatToSay, doctorKits[].bringToAppointment[]
- Do not modify immutable identifiers or care-plan structure such as diagnosisId, suggestedTests, recommendedTests, priority, specialty, concerningSymptoms, and allClear
- Return valid JSON only, same schema as input`;

type RewriteSource =
  | 'live_openai_rewrite_success'
  | 'live_groq_rewrite_fallback_success'
  | 'live_groq_rewrite_success'
  | 'fallback_no_api_keys'
  | 'fallback_no_groq_key'
  | 'fallback_openai_http_error'
  | 'fallback_groq_http_error'
  | 'fallback_openai_parse_failed'
  | 'fallback_parse_failed'
  | 'fallback_openai_schema_failed'
  | 'fallback_schema_failed'
  | 'fallback_openai_exception'
  | 'fallback_exception';

export interface RewriteToneResult {
  data: DeepAnalyzeResult;
  rewriteSource: RewriteSource;
  model?: string;
  status?: number;
  errorSnippet?: string;
}

async function callOpenAIRewrite(
  report: DeepAnalyzeResult,
  openaiKey: string,
): Promise<RewriteToneResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);

  try {
    const response = await fetch(OPENAI_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${openaiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: OPENAI_SYNTHESIS_MODEL,
        messages: [
          { role: 'system', content: SAFETY_SYSTEM_PROMPT },
          { role: 'user', content: JSON.stringify(report) },
        ],
        max_completion_tokens: 2500,
        response_format: { type: 'json_object' },
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errBody = await response.text().catch(() => '');
      return {
        data: report,
        rewriteSource: 'fallback_openai_http_error',
        model: OPENAI_SYNTHESIS_MODEL,
        status: response.status,
        errorSnippet: errBody.slice(0, 200),
      };
    }

    const data = await response.json();
    const content: string = data.choices?.[0]?.message?.content ?? '';
    const parsed = parseJsonObject(content);
    if (!parsed) {
      return {
        data: report,
        rewriteSource: 'fallback_openai_parse_failed',
        model: OPENAI_SYNTHESIS_MODEL,
        errorSnippet: content.slice(0, 200),
      };
    }

    const validation = validateDeepAnalyzeSchema(parsed);
    if (!validation.ok) {
      return {
        data: report,
        rewriteSource: 'fallback_openai_schema_failed',
        model: OPENAI_SYNTHESIS_MODEL,
        errorSnippet: validation.reason.slice(0, 200),
      };
    }

    return {
      data: mergeWithImmutableFields(report, validation.data),
      rewriteSource: 'live_openai_rewrite_success',
      model: OPENAI_SYNTHESIS_MODEL,
    };
  } catch (err) {
    return {
      data: report,
      rewriteSource: 'fallback_openai_exception',
      model: OPENAI_SYNTHESIS_MODEL,
      errorSnippet: String(err).slice(0, 200),
    };
  } finally {
    clearTimeout(timeout);
  }
}

function mergeStringArray(original: string[], rewritten?: string[]): string[] {
  return original.map((item, index) => rewritten?.[index]?.trim() || item);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function computeBackoffDelayMs(attemptIndex: number): number {
  const baseDelay = GROQ_BACKOFF_BASE_MS * (2 ** attemptIndex);
  const jitter = Math.floor(Math.random() * 250);
  return baseDelay + jitter;
}

function parseJsonObject(raw: string): Record<string, unknown> | null {
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) return null;
  try {
    return JSON.parse(jsonMatch[0]) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function mergeWithImmutableFields(
  original: DeepAnalyzeResult,
  rewritten: DeepAnalyzeResult,
): DeepAnalyzeResult {
  return {
    ...original,
    personalizedSummary: rewritten.personalizedSummary,
    summaryPoints: original.summaryPoints
      ? mergeStringArray(original.summaryPoints, rewritten.summaryPoints)
      : (rewritten.summaryPoints ?? original.summaryPoints),
    insights: original.insights.map((item, index) => ({
      diagnosisId: item.diagnosisId,
      personalNote: rewritten.insights[index]?.personalNote?.trim() || item.personalNote,
    })),
    declinedSuspicions: original.declinedSuspicions?.map((item, index) => ({
      diagnosisId: item.diagnosisId,
      reason: rewritten.declinedSuspicions?.[index]?.reason?.trim() || item.reason,
    })),
    recoveryOutlook: rewritten.recoveryOutlook ?? original.recoveryOutlook,
    nextSteps: rewritten.nextSteps,
    doctorKitSummary: rewritten.doctorKitSummary ?? original.doctorKitSummary,
    doctorKitQuestions: mergeStringArray(original.doctorKitQuestions, rewritten.doctorKitQuestions),
    doctorKitArguments: mergeStringArray(original.doctorKitArguments, rewritten.doctorKitArguments),
    recommendedDoctors: original.recommendedDoctors.map((doctor, index) => ({
      ...doctor,
      reason: rewritten.recommendedDoctors[index]?.reason?.trim() || doctor.reason,
      symptomsToDiscuss: mergeStringArray(
        doctor.symptomsToDiscuss,
        rewritten.recommendedDoctors[index]?.symptomsToDiscuss,
      ),
    })),
    doctorKits: original.doctorKits.map((kit, index) => ({
      ...kit,
      openingSummary: rewritten.doctorKits[index]?.openingSummary?.trim() || kit.openingSummary,
      discussionPoints: mergeStringArray(
        kit.discussionPoints,
        rewritten.doctorKits[index]?.discussionPoints,
      ),
      ...(kit.whatToSay || rewritten.doctorKits[index]?.whatToSay
        ? { whatToSay: rewritten.doctorKits[index]?.whatToSay?.trim() || kit.whatToSay }
        : {}),
      ...(kit.bringToAppointment || rewritten.doctorKits[index]?.bringToAppointment
        ? {
            bringToAppointment: mergeStringArray(
              kit.bringToAppointment ?? [],
              rewritten.doctorKits[index]?.bringToAppointment,
            ),
          }
        : {}),
    })),
    allClear: original.allClear,
  };
}

/**
 * V6: Primary Groq synthesis call. Takes the full synthesis prompt (built by
 * buildGroqSynthesisPromptV6 or buildAllClearPrompt) and returns a validated
 * DeepAnalyzeResult. Returns null on timeout, parse failure, or missing API key
 * so the caller can fall back gracefully.
 */
async function callGroqSynthesis(
  synthesisPrompt: string,
  groqKey: string,
  model: string,
  timeoutMs: number,
): Promise<{
  data: DeepAnalyzeResult | null;
  source:
    | 'live_groq_primary_success'
    | 'live_groq_fallback_success'
    | 'fallback_groq_http_error'
    | 'fallback_groq_parse_failed'
    | 'fallback_groq_schema_failed'
    | 'fallback_groq_exception';
  model: string;
  status?: number;
  errorSnippet?: string;
}> {
  for (let attempt = 0; attempt <= GROQ_MAX_429_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(GROQ_API_URL, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${groqKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model,
          messages: [
            {
              role: 'system',
              content:
                'You output valid JSON only. No markdown, no thinking, no explanations, no preamble. Start your response immediately with { and end with }.',
            },
            { role: 'user', content: synthesisPrompt },
          ],
          max_tokens: 3500,
          temperature: 0.3,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errBody = await response.text().catch(() => '');
        if (response.status === 429 && attempt < GROQ_MAX_429_RETRIES) {
          const delayMs = computeBackoffDelayMs(attempt);
          console.warn(
            `[Groq synthesis][${model}] 429 rate limit on attempt ${attempt + 1}; retrying in ${delayMs}ms`,
          );
          await sleep(delayMs);
          continue;
        }

        console.warn(`[Groq synthesis][${model}] API error: ${response.status}`, errBody.slice(0, 300));
        return {
          data: null,
          source: 'fallback_groq_http_error',
          model,
          status: response.status,
          errorSnippet: errBody.slice(0, 200),
        };
      }

      const data = await response.json();
      const content: string = data.choices?.[0]?.message?.content ?? '';
      const parsed = parseJsonObject(content);
      if (!parsed) {
        console.warn(`[Groq synthesis][${model}] Could not parse JSON. Raw:`, content.slice(0, 500));
        return {
          data: null,
          source: 'fallback_groq_parse_failed',
          model,
          errorSnippet: content.slice(0, 200),
        };
      }

      const validation = validateDeepAnalyzeSchema(parsed);
      if (!validation.ok) {
        console.warn(`[Groq synthesis][${model}] Schema failed: ${validation.reason} | keys: ${Object.keys(parsed).join(', ')}`);
        return {
          data: null,
          source: 'fallback_groq_schema_failed',
          model,
          errorSnippet: validation.reason.slice(0, 200),
        };
      }

      return {
        data: validation.data,
        source: model === GROQ_SYNTHESIS_MODEL ? 'live_groq_primary_success' : 'live_groq_fallback_success',
        model,
      };
    } catch (err) {
      console.warn(`[Groq synthesis][${model}] Error: ${String(err)}`);
      return {
        data: null,
        source: 'fallback_groq_exception',
        model,
        errorSnippet: String(err).slice(0, 200),
      };
    } finally {
      clearTimeout(timeout);
    }
  }

  return {
    data: null,
    source: 'fallback_groq_http_error',
    model,
    status: 429,
    errorSnippet: 'Groq rate limit persisted after retries',
  };
}

async function callOpenAISynthesis(
  synthesisPrompt: string,
  openaiKey: string,
  timeoutMs: number,
): Promise<{
  data: DeepAnalyzeResult | null;
  source:
    | 'live_openai_fallback_success'
    | 'fallback_openai_http_error'
    | 'fallback_openai_parse_failed'
    | 'fallback_openai_schema_failed'
    | 'fallback_openai_exception';
  model: string;
  status?: number;
  errorSnippet?: string;
}> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(OPENAI_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${openaiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: OPENAI_SYNTHESIS_MODEL,
        messages: [
          {
            role: 'system',
            content:
              'You output valid JSON only. No markdown, no thinking, no explanations, no preamble. Start your response immediately with { and end with }.',
          },
          { role: 'user', content: synthesisPrompt },
        ],
        max_completion_tokens: 3500,
        response_format: { type: 'json_object' },
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errBody = await response.text().catch(() => '');
      console.warn(`[OpenAI synthesis][${OPENAI_SYNTHESIS_MODEL}] API error: ${response.status}`, errBody.slice(0, 300));
      return {
        data: null,
        source: 'fallback_openai_http_error',
        model: OPENAI_SYNTHESIS_MODEL,
        status: response.status,
        errorSnippet: errBody.slice(0, 200),
      };
    }

    const data = await response.json();
    const content: string = data.choices?.[0]?.message?.content ?? '';
    const parsed = parseJsonObject(content);
    if (!parsed) {
      console.warn(`[OpenAI synthesis] Could not parse JSON. Raw:`, content.slice(0, 500));
      return {
        data: null,
        source: 'fallback_openai_parse_failed',
        model: OPENAI_SYNTHESIS_MODEL,
        errorSnippet: content.slice(0, 200),
      };
    }

    const validation = validateDeepAnalyzeSchema(parsed);
    if (!validation.ok) {
      console.warn(`[OpenAI synthesis] Schema failed: ${validation.reason} | keys: ${Object.keys(parsed).join(', ')}`);
      return {
        data: null,
        source: 'fallback_openai_schema_failed',
        model: OPENAI_SYNTHESIS_MODEL,
        errorSnippet: validation.reason.slice(0, 200),
      };
    }

    console.info('[OpenAI synthesis] Success via fallback');
    return {
      data: validation.data,
      source: 'live_openai_fallback_success',
      model: OPENAI_SYNTHESIS_MODEL,
    };
  } catch (err) {
    console.warn(`[OpenAI synthesis] Error: ${String(err)}`);
    return {
      data: null,
      source: 'fallback_openai_exception',
      model: OPENAI_SYNTHESIS_MODEL,
      errorSnippet: String(err).slice(0, 200),
    };
  } finally {
    clearTimeout(timeout);
  }
}

export async function synthesizeNarrativeWithGroqV6(
  synthesisPrompt: string | { primaryPrompt: string; fallbackPrompt?: string },
): Promise<{
  data: DeepAnalyzeResult | null;
  synthesisSource:
    | 'live_openai_primary_success'
    | 'live_groq_primary_success'
    | 'live_groq_fallback_success'
    | 'live_openai_fallback_success'
    | 'fallback_no_api_keys'
    | 'fallback_groq_http_error'
    | 'fallback_groq_parse_failed'
    | 'fallback_groq_schema_failed'
    | 'fallback_groq_exception'
    | 'fallback_openai_http_error'
    | 'fallback_openai_parse_failed'
    | 'fallback_openai_schema_failed'
    | 'fallback_openai_exception';
  model?: string;
  status?: number;
  errorSnippet?: string;
}> {
  const groqKey = process.env.GROQ_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;
  const primaryPrompt = typeof synthesisPrompt === 'string'
    ? synthesisPrompt
    : synthesisPrompt.primaryPrompt;
  const fallbackPrompt = typeof synthesisPrompt === 'string'
    ? synthesisPrompt
    : (synthesisPrompt.fallbackPrompt ?? synthesisPrompt.primaryPrompt);

  // 1. Prefer OpenAI when available and do not fan out to Groq in that case.
  if (openaiKey) {
    const openaiPrimary = await callOpenAISynthesis(primaryPrompt, openaiKey, 45_000);
    return openaiPrimary.data
      ? {
          data: openaiPrimary.data,
          synthesisSource: 'live_openai_primary_success',
          model: openaiPrimary.model,
        }
      : {
          data: null,
          synthesisSource: openaiPrimary.source,
          model: openaiPrimary.model,
          status: openaiPrimary.status,
          errorSnippet: openaiPrimary.errorSnippet,
        };
  }

  // 2. Try primary Groq model (45s)
  if (groqKey) {
    const primary = await callGroqSynthesis(primaryPrompt, groqKey, GROQ_SYNTHESIS_MODEL, 45_000);
    if (primary.data) {
      return {
        data: primary.data,
        synthesisSource: primary.source,
        model: primary.model,
      };
    }

    // 3. Try smaller Groq model (30s)
    console.warn('[synthesis] Primary Groq failed — retrying with Groq fallback model');
    const groqFallback = await callGroqSynthesis(fallbackPrompt, groqKey, GROQ_SYNTHESIS_FALLBACK_MODEL, 30_000);
    if (groqFallback.data) {
      return {
        data: groqFallback.data,
        synthesisSource: groqFallback.source,
        model: groqFallback.model,
      };
    }

    if (!openaiKey) {
      return {
        data: null,
        synthesisSource: groqFallback.source,
        model: groqFallback.model,
        status: groqFallback.status,
        errorSnippet: groqFallback.errorSnippet,
      };
    }
  }

  return {
    data: null,
    synthesisSource: 'fallback_no_api_keys',
  };
}

export async function rewriteDeepAnalyzeTone(
  report: DeepAnalyzeResult,
): Promise<RewriteToneResult> {
  const groqKey = process.env.GROQ_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;

  if (openaiKey) {
    return callOpenAIRewrite(report, openaiKey);
  }

  if (!groqKey) {
    return {
      data: report,
      rewriteSource: openaiKey ? 'fallback_no_api_keys' : 'fallback_no_groq_key',
    };
  }

  try {
    for (let attempt = 0; attempt <= GROQ_MAX_429_RETRIES; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);

      try {
        const groqResponse = await fetch(GROQ_API_URL, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${groqKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            model: GROQ_MODEL,
            messages: [
              { role: 'system', content: SAFETY_SYSTEM_PROMPT },
              { role: 'user', content: JSON.stringify(report) },
            ],
            max_tokens: 2500,
            temperature: 0.2,
          }),
          signal: controller.signal,
        });
        if (!groqResponse.ok) {
          const errBody = await groqResponse.text().catch(() => '');
          if (groqResponse.status === 429 && attempt < GROQ_MAX_429_RETRIES) {
            const delayMs = computeBackoffDelayMs(attempt);
            console.warn(
              `[Groq rewrite][${GROQ_MODEL}] 429 rate limit on attempt ${attempt + 1}; retrying in ${delayMs}ms`,
            );
            await sleep(delayMs);
            continue;
          }

          return {
            data: report,
            rewriteSource: 'fallback_groq_http_error',
            model: GROQ_MODEL,
            status: groqResponse.status,
            errorSnippet: errBody.slice(0, 200),
          };
        }

        const groqData = await groqResponse.json();
        const content: string = groqData.choices?.[0]?.message?.content ?? '';
        const parsed = parseJsonObject(content);
        if (!parsed) {
          return {
            data: report,
            rewriteSource: 'fallback_parse_failed',
            model: GROQ_MODEL,
            errorSnippet: content.slice(0, 200),
          };
        }

        const validation = validateDeepAnalyzeSchema(parsed);
        if (!validation.ok) {
          return {
            data: report,
            rewriteSource: 'fallback_schema_failed',
            model: GROQ_MODEL,
            errorSnippet: validation.reason.slice(0, 200),
          };
        }

        return {
          data: mergeWithImmutableFields(report, validation.data),
          rewriteSource: openaiKey ? 'live_groq_rewrite_fallback_success' : 'live_groq_rewrite_success',
          model: GROQ_MODEL,
        };
      } finally {
        clearTimeout(timeout);
      }
    }

    return {
      data: report,
      rewriteSource: 'fallback_groq_http_error',
      model: GROQ_MODEL,
      status: 429,
      errorSnippet: 'Groq rate limit persisted after retries',
    };
  } catch {
    return {
      data: report,
      rewriteSource: 'fallback_exception',
      model: GROQ_MODEL,
    };
  }
}
