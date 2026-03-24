'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAssessment } from '@/src/hooks/useAssessment';
import {
  createOfflineDeepResult,
  getConfiguredAiMode,
  getDeepAnalysisWithFallback,
  storeDeepResult,
  readStoredDeepResult,
  readStoredBayesianScores,
  readStoredBayesianAnswers,
  readStoredMLScores,
} from '@/src/lib/medgemma';
import { BlobCharacter } from '@/src/components/ui/BlobCharacter';

const loadingMessages = [
  'Reading symptom patterns',
  'Cross-checking likely drivers',
  'Drafting doctor-ready questions',
  'Building your coaching plan',
];

export default function ProcessingPage() {
  const router = useRouter();
  const { answers, hydrated } = useAssessment();
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const aiMode = getConfiguredAiMode();

  // Cycle through loading messages
  useEffect(() => {
    if (!hydrated) return;
    const interval = window.setInterval(() => {
      setStepIndex((current) => (current + 1) % loadingMessages.length);
    }, 1200);
    return () => window.clearInterval(interval);
  }, [hydrated]);

  useEffect(() => {
    if (!hydrated) return;

    // Skip if already cached (e.g. user navigated back and forward)
    const cached = readStoredDeepResult();
    if (cached) {
      router.replace('/results');
      return;
    }

    let cancelled = false;

    const run = async () => {
      // Scores come from Bayesian layer (clarify page) or fall back to raw ML scores
      const mlScores: Record<string, number> | undefined =
        readStoredBayesianScores() ?? readStoredMLScores() ?? undefined;

      // Clarification Q&A from Bayesian layer — may be null if clarify was skipped
      const clarificationQA = readStoredBayesianAnswers() ?? undefined;

      try {
        const [result] = await Promise.all([
          getDeepAnalysisWithFallback(answers, mlScores, clarificationQA),
          new Promise((resolve) => window.setTimeout(resolve, 2600)),
        ]);

        if (cancelled) return;
        storeDeepResult(result);
        router.replace('/results');
      } catch {
        if (cancelled) return;
        storeDeepResult(createOfflineDeepResult(answers));
        setError('We could not build the report automatically, so HalfFull prepared a local fallback report instead.');
        router.replace('/results');
      }
    };

    void run();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  if (!hydrated) {
    return (
      <div className="phone-frame flex items-center justify-center">
        <p className="text-sm text-[var(--color-ink-soft)]">Loading...</p>
      </div>
    );
  }

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex flex-1 items-center px-5 py-6">
        <div className="mx-auto flex w-full max-w-lg flex-col gap-5">
          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-5 py-8 text-center shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="mx-auto mb-5 flex h-24 w-24 items-center justify-center rounded-full bg-[rgba(119,101,244,0.08)]">
              <BlobCharacter
                className="h-16 w-16 animate-[pulse_2.4s_ease-in-out_infinite]"
                accent="lime"
                mood="gentle"
              />
            </div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
              HalfFull is preparing your report
            </p>
            <h1 className="text-[2rem] font-bold leading-[1] tracking-[-0.05em] text-[var(--color-ink)]">
              Thinking through the full picture
            </h1>
            <p className="mt-3 text-base leading-7 text-[var(--color-ink-soft)]">
              {loadingMessages[stepIndex]}
            </p>
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
              {aiMode === 'live' ? 'Mode: live with automatic demo fallback' : `Mode: ${aiMode}`}
            </p>

            <div className="mx-auto mt-6 h-3 w-56 rounded-full bg-[rgba(151,166,210,0.2)] p-[3px]">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#7765f4_0%,#d7f068_100%)] transition-all duration-700"
                style={{ width: `${((stepIndex + 1) / loadingMessages.length) * 100}%` }}
              />
            </div>
          </section>

          {error && (
            <div className="section-card px-5 py-4">
              <p className="text-sm leading-6 text-[var(--color-ink-soft)]">
                {error}
              </p>
              <button
                type="button"
                onClick={() => router.replace('/results')}
                className="mt-4 w-full rounded-full bg-[#09090f] px-5 py-4 text-base font-bold text-white"
              >
                Open report
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
