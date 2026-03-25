import { buildMockDeepResult, buildOfflineDeepResult } from '@/src/lib/mockResults';
// ─── Storage keys ─────────────────────────────────────────────────────────────

export const MEDGEMMA_STORAGE_KEY    = 'halffull_medgemma_v1';
export const DEEP_STORAGE_KEY        = 'halffull_deep_v1';
export const FOLLOWUP_STORAGE_KEY    = 'halffull_followup_v1';
export const ML_SCORES_KEY           = 'halffull_ml_scores_v1';
export const BAYESIAN_SCORES_KEY     = 'halffull_bayesian_scores_v1';
export const BAYESIAN_ANSWERS_KEY    = 'halffull_bayesian_answers_v1';
export const CONFIRMED_CONDITIONS_KEY = 'halffull_confirmed_v1';

export type AiMode = 'live' | 'mock' | 'offline';
export type AiResultSource = 'live' | 'mock' | 'offline';

// ─── Basic result (from /api/analyze) ─────────────────────────────────────────

export interface MedGemmaInsight {
  diagnosisId: string;
  personalNote: string;
}

export interface RecommendedDoctor {
  specialty: string;
  priority: string;
  reason: string;
  symptomsToDiscuss: string[];
  suggestedTests: string[];
}

export interface DoctorKit {
  specialty: string;
  openingSummary: string;
  concerningSymptoms: string[];
  recommendedTests: string[];
  discussionPoints: string[];
}

export interface MedGemmaResult {
  personalizedSummary: string;
  insights: MedGemmaInsight[];
  nextSteps: string;
}

// ─── Deep analysis result (from /api/deep-analyze) ────────────────────────────

export interface CoachingTip {
  category: string;
  tip: string;
  timeframe: string;
}

export interface DeepMedGemmaResult extends MedGemmaResult {
  /** AI-generated symptom narrative to open the doctor conversation */
  doctorKitSummary?: string;
  /** AI-generated questions to ask the doctor (replaces rule-based when present) */
  doctorKitQuestions?: string[];
  /** AI-generated arguments for requesting additional tests */
  doctorKitArguments?: string[];
  /** AI-selected clinician recommendations for this case */
  recommendedDoctors?: RecommendedDoctor[];
  /** Doctor-specific kits aligned with recommendedDoctors */
  doctorKits?: DoctorKit[];
  /** Energy-saving and lifestyle coaching tips */
  coachingTips?: CoachingTip[];
  /** Source metadata used to label fallback content honestly in the UI */
  meta?: {
    mode: AiResultSource;
    label: string;
    fallback: boolean;
  };
}

// ─── Bayesian clarification Q&A (stored after /clarify, passed to MedGemma) ───

export interface ClarificationQAPair {
  /** Human-readable group label, e.g. "Thyroid · 78%" or "Mood" */
  group: string;
  /** Full question text as shown to the patient */
  question: string;
  /** Selected answer label, e.g. "Yes, it's much drier" */
  answer: string;
}

export type BayesianClarificationRecord = ClarificationQAPair[];

// ─── Bayesian layer types (from /api/bayesian-questions and /api/bayesian-update) ──

export interface BayesianAnswerOption {
  value: string;
  label: string;
}

export interface BayesianQuestion {
  id: string;
  text: string;
  answer_type: 'binary' | 'ordinal' | 'categorical';
  answer_options: BayesianAnswerOption[];
}

export interface ConfounderQuestion extends BayesianQuestion {
  confounder: string;   // "depression" | "anxiety"
}

export interface ConditionQuestion {
  condition: string;
  probability: number;
  question: BayesianQuestion;
}

export interface BayesianQuestionsResult {
  confounder_questions: ConfounderQuestion[];
  condition_questions:  ConditionQuestion[];
}

export interface BayesianUpdateResult {
  posteriorScores: Record<string, number>;
  details:         Record<string, unknown>;
}

// ─── Storage helpers ──────────────────────────────────────────────────────────

export function readStoredMedGemmaResult(): MedGemmaResult | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(MEDGEMMA_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MedGemmaResult) : null;
  } catch {
    return null;
  }
}

export function storeMedGemmaResult(result: MedGemmaResult): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(MEDGEMMA_STORAGE_KEY, JSON.stringify(result));
}

export function readStoredDeepResult(): DeepMedGemmaResult | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(DEEP_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DeepMedGemmaResult) : null;
  } catch {
    return null;
  }
}

export function storeDeepResult(result: DeepMedGemmaResult): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(DEEP_STORAGE_KEY, JSON.stringify(result));
}

export function storeBayesianAnswers(qa: BayesianClarificationRecord): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(BAYESIAN_ANSWERS_KEY, JSON.stringify(qa));
}

export function readStoredBayesianAnswers(): BayesianClarificationRecord | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(BAYESIAN_ANSWERS_KEY);
    return raw ? (JSON.parse(raw) as BayesianClarificationRecord) : null;
  } catch {
    return null;
  }
}

export function clearStoredMedGemmaResult(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(MEDGEMMA_STORAGE_KEY);
  window.sessionStorage.removeItem(DEEP_STORAGE_KEY);
  window.sessionStorage.removeItem(ML_SCORES_KEY);
  window.sessionStorage.removeItem(BAYESIAN_SCORES_KEY);
  window.sessionStorage.removeItem(BAYESIAN_ANSWERS_KEY);
  window.sessionStorage.removeItem(CONFIRMED_CONDITIONS_KEY);
}

export function storeConfirmedConditions(conditions: string[]): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(CONFIRMED_CONDITIONS_KEY, JSON.stringify(conditions));
}

export function readStoredConfirmedConditions(): string[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(CONFIRMED_CONDITIONS_KEY);
    return raw ? (JSON.parse(raw) as string[]) : null;
  } catch {
    return null;
  }
}

export function storeBayesianScores(scores: Record<string, number>): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(BAYESIAN_SCORES_KEY, JSON.stringify(scores));
}

export function readStoredBayesianScores(): Record<string, number> | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(BAYESIAN_SCORES_KEY);
    return raw ? (JSON.parse(raw) as Record<string, number>) : null;
  } catch {
    return null;
  }
}

export function storeMLScores(scores: Record<string, number>): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(ML_SCORES_KEY, JSON.stringify(scores));
}

export function readStoredMLScores(): Record<string, number> | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(ML_SCORES_KEY);
    return raw ? (JSON.parse(raw) as Record<string, number>) : null;
  } catch {
    return null;
  }
}

// ─── API fetch helpers ────────────────────────────────────────────────────────

export interface MLScoreResult {
  scores: Record<string, number>;
  confirmed: string[];
}

/** Call /api/score to run the ML model pipeline and get condition probabilities + confirmed list */
export async function fetchMLScores(
  answers: Record<string, unknown>
): Promise<MLScoreResult> {
  const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || '';
  const response = await fetch(`${backendBaseUrl}/api/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error((err as { error?: string }).error ?? `HTTP ${response.status}`);
  }

  const data = await response.json() as { scores?: Record<string, number>; confirmed?: string[]; error?: string };
  if (data.error) throw new Error(data.error);
  return { scores: data.scores ?? {}, confirmed: data.confirmed ?? [] };
}

export function getConfiguredAiMode(): AiMode {
  const raw = process.env.NEXT_PUBLIC_AI_MODE?.trim().toLowerCase();
  return raw === 'mock' || raw === 'offline' ? raw : 'live';
}

async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  label: string
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;

  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/** Basic insights — called as fallback if deep-analyze fails */
export async function fetchMedGemmaInsights(
  answers: Record<string, unknown>,
  mlScores?: Record<string, number>
): Promise<MedGemmaResult> {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers, mlScores }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error ?? `HTTP ${response.status}`);
  }

  return response.json() as Promise<MedGemmaResult>;
}

/** Deep analysis — comprehensive report including doctor kit + coaching tips */
export async function fetchDeepAnalysis(
  answers: Record<string, unknown>,
  mlScores?: Record<string, number>,
  clarificationQA?: BayesianClarificationRecord,
  confirmedConditions?: string[],
): Promise<DeepMedGemmaResult> {
  const response = await fetch('/api/deep-analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers, mlScores, clarificationQA, confirmedConditions }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error ?? `HTTP ${response.status}`);
  }

  return response.json() as Promise<DeepMedGemmaResult>;
}

/** Fetch structured Bayesian follow-up questions for triggered conditions */
export async function fetchBayesianQuestions(
  mlScores: Record<string, number>,
  patientSex?: string,
): Promise<BayesianQuestionsResult> {
  const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || '';
  const response = await fetch(`${backendBaseUrl}/api/bayesian-questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mlScores, patientSex }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error((err as { error?: string }).error ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<BayesianQuestionsResult>;
}

/** Run Bayesian update and return posterior scores */
export async function fetchBayesianUpdate(
  mlScores: Record<string, number>,
  confounderAnswers: Record<string, number>,
  answersByCondition: Record<string, Record<string, string>>,
  patientSex?: string,
): Promise<BayesianUpdateResult> {
  const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || '';
  const response = await fetch(`${backendBaseUrl}/api/bayesian-update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mlScores, confounderAnswers, answersByCondition, patientSex }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error((err as { error?: string }).error ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<BayesianUpdateResult>;
}

// ─── Utility ──────────────────────────────────────────────────────────────────

export async function fetchMLScoresWithTimeout(
  answers: Record<string, unknown>,
  timeoutMs = 40000
): Promise<MLScoreResult> {
  return withTimeout(fetchMLScores(answers), timeoutMs, 'Assessment scoring');
}

export async function fetchBayesianQuestionsWithTimeout(
  mlScores: Record<string, number>,
  patientSex?: string,
  timeoutMs = 30000,
): Promise<BayesianQuestionsResult> {
  return withTimeout(fetchBayesianQuestions(mlScores, patientSex), timeoutMs, 'Clarify questions');
}

export async function fetchBayesianUpdateWithTimeout(
  mlScores: Record<string, number>,
  confounderAnswers: Record<string, number>,
  answersByCondition: Record<string, Record<string, string>>,
  patientSex?: string,
  timeoutMs = 15000,
): Promise<BayesianUpdateResult> {
  return withTimeout(
    fetchBayesianUpdate(mlScores, confounderAnswers, answersByCondition, patientSex),
    timeoutMs,
    'Clarify update'
  );
}

function buildStoredDeepResult(
  source: AiResultSource,
  base: DeepMedGemmaResult
): DeepMedGemmaResult {
  const label =
    source === 'live'
      ? 'Live MedGemma'
      : source === 'mock'
        ? 'Demo fallback'
        : 'Offline fallback';

  return {
    ...base,
    meta: {
      mode: source,
      label,
      fallback: source !== 'live',
    },
  };
}

export function createMockDeepResult(answers: Record<string, unknown>): DeepMedGemmaResult {
  return buildStoredDeepResult('mock', buildMockDeepResult(answers));
}

export function createOfflineDeepResult(answers: Record<string, unknown>): DeepMedGemmaResult {
  return buildStoredDeepResult('offline', buildOfflineDeepResult(answers));
}

export async function getDeepAnalysisWithFallback(
  answers: Record<string, unknown>,
  mlScores?: Record<string, number>,
  clarificationQA?: BayesianClarificationRecord,
  confirmedConditions?: string[],
  timeoutMs = 85000  // matches the 90s abort controller in /api/deep-analyze
): Promise<DeepMedGemmaResult> {
  const mode = getConfiguredAiMode();

  if (mode === 'offline') {
    return createOfflineDeepResult(answers);
  }

  if (mode === 'mock') {
    return createMockDeepResult(answers);
  }

  try {
    const liveResult = await withTimeout(
      fetchDeepAnalysis(answers, mlScores, clarificationQA, confirmedConditions),
      timeoutMs,
      'Live AI analysis'
    );
    return buildStoredDeepResult('live', liveResult);
  } catch (err) {
    console.error('[getDeepAnalysisWithFallback] Live analysis failed, using mock fallback:', err);
    try {
      return createMockDeepResult(answers);
    } catch {
      return createOfflineDeepResult(answers);
    }
  }
}

/** Returns the personalNote for a given diagnosis id, if one exists */
export function getInsightForDiagnosis(
  result: MedGemmaResult | null,
  diagnosisId: string
): string | undefined {
  return result?.insights.find((i) => i.diagnosisId === diagnosisId)?.personalNote;
}
