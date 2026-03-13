'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAssessment } from '@/src/hooks/useAssessment';
import { computeResults } from '@/src/lib/mockResults';
import {
  fetchFollowUpQuestions,
  readStoredFollowUp,
  storeFollowUp,
} from '@/src/lib/medgemma';
import type { FollowUpResult } from '@/src/lib/medgemma';
import { BlobCharacter } from '@/src/components/ui/BlobCharacter';

/** Fallback questions used when MedGemma is unavailable */
function buildFallbackQuestions(
  answers: Record<string, unknown>,
  topDiagnosisTitles: string[]
): string[] {
  const questions = [
    'When your energy drops, what does it feel like in your body and mind?',
  ];
  if (topDiagnosisTitles.length > 0) {
    questions.push(
      `Which of these feels most disruptive right now: ${topDiagnosisTitles.join(', ')}?`
    );
  } else {
    questions.push('What pattern feels most important for a doctor to understand quickly?');
  }
  const additionalSymptoms = String(answers['q6.0'] ?? '').trim();
  questions.push(
    additionalSymptoms
      ? `You mentioned "${additionalSymptoms}". When does that show up most?`
      : 'Is there anything that makes your symptoms better, worse, or more predictable?'
  );
  return questions.slice(0, 3);
}

type LoadPhase = 'loading' | 'ready';

export default function ClarifyPage() {
  const router = useRouter();
  const { answers, hydrated, setAnswer } = useAssessment();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<LoadPhase>('loading');
  const [followUp, setFollowUp] = useState<FollowUpResult | null>(null);

  const { diagnoses, summaryLine } = computeResults(answers);
  const topDiagnosisTitles = diagnoses.slice(0, 3).map((d) => d.title);

  // Load MedGemma follow-up questions once assessment is hydrated
  useEffect(() => {
    if (!hydrated) return;

    // Check session cache first to avoid re-generating on back-navigation
    const cached = readStoredFollowUp();
    if (cached) {
      setFollowUp(cached);
      setPhase('ready');
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        const result = await fetchFollowUpQuestions(answers, diagnoses);
        if (cancelled) return;
        storeFollowUp(result);
        setFollowUp(result);
      } catch {
        if (cancelled) return;
        // Fall back to rule-based questions when MedGemma is unavailable
        const fallback: FollowUpResult = {
          hypotheses: [],
          questions: buildFallbackQuestions(answers, topDiagnosisTitles),
        };
        setFollowUp(fallback);
      } finally {
        if (!cancelled) setPhase('ready');
      }
    };

    void load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  const questions = followUp?.questions ?? [];

  const allAnswered = questions.every((_, index) => {
    const key = `clarify_${index + 1}`;
    const value = drafts[key] ?? String(answers[key] ?? '');
    return value.trim().length > 0;
  });

  if (!hydrated || phase === 'loading') {
    return (
      <div className="phone-frame flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 px-8 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-[rgba(119,101,244,0.08)]">
            <BlobCharacter
              className="h-14 w-14 animate-[pulse_2.4s_ease-in-out_infinite]"
              accent="lime"
              mood="gentle"
            />
          </div>
          <p className="text-sm font-medium text-[var(--color-ink-soft)]">
            Generating personalised questions…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex-1 px-5 py-6">
        <div className="mx-auto flex max-w-lg flex-col gap-5">
          {/* Header */}
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <span className="text-[var(--color-ink-soft)]">Clarify</span>
          </div>

          {/* Hero card */}
          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="absolute right-5 top-5">
              <BlobCharacter className="h-16 w-16" accent="lime" mood="gentle" />
            </div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
              Final touch
            </p>
            <h1 className="text-[2rem] font-bold leading-[1] tracking-[-0.05em] text-[var(--color-ink)]">
              A few quick clarifying questions
            </h1>
            <p className="mt-3 max-w-[18rem] text-sm leading-6 text-[var(--color-ink-soft)]">
              {summaryLine}
            </p>

            {/* MedGemma hypotheses pills */}
            {followUp && followUp.hypotheses.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {followUp.hypotheses.map((h, i) => (
                  <span
                    key={i}
                    className="rounded-full bg-[var(--color-lime)] px-3 py-1 text-[10px] font-bold text-[var(--color-ink)]"
                  >
                    {h}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* Question cards */}
          <div className="space-y-4">
            {questions.map((question, index) => {
              const key = `clarify_${index + 1}`;
              const value = drafts[key] ?? String(answers[key] ?? '');
              const target = followUp?.questionTargets?.[index];

              return (
                <div key={key} className="section-card px-5 py-5">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <div className="inline-flex rounded-full bg-[var(--color-accent-soft)] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--color-ink)]">
                      Question {index + 1}
                    </div>
                    {target && (
                      <div className="inline-flex items-center gap-1 rounded-full border border-[rgba(151,166,210,0.3)] bg-white px-3 py-1 text-[10px] font-medium text-[var(--color-ink-soft)]">
                        <span className="text-[8px]">🔍</span>
                        {target}
                      </div>
                    )}
                  </div>
                  <p className="text-base font-medium leading-6 text-[var(--color-ink)]">
                    {question}
                  </p>
                  <textarea
                    value={value}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setDrafts((current) => ({ ...current, [key]: nextValue }));
                      setAnswer(key, nextValue);
                    }}
                    rows={4}
                    placeholder="Type your answer here..."
                    className="mt-4 w-full resize-none rounded-[1.35rem] border border-[rgba(151,166,210,0.28)] bg-white px-4 py-3 text-base text-[var(--color-ink)] placeholder-[var(--color-ink-soft)] focus:border-[var(--color-accent)] focus:outline-none"
                  />
                </div>
              );
            })}
          </div>

          <button
            type="button"
            disabled={!allAnswered}
            onClick={() => router.push('/processing')}
            className={[
              'w-full rounded-full px-5 py-4 text-base font-bold transition-all',
              allAnswered
                ? 'bg-[#09090f] text-white shadow-[0_10px_24px_rgba(9,9,15,0.22)]'
                : 'bg-white/50 text-[rgba(9,9,15,0.34)]',
            ].join(' ')}
          >
            Prepare my report
          </button>
        </div>
      </main>
    </div>
  );
}
