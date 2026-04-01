'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAssessment } from '@/src/hooks/useAssessment';
import {
  fetchBayesianQuestionsWithTimeout,
  fetchBayesianUpdateWithTimeout,
  fetchMLScoresWithTimeout,
  readStoredMLScores,
  storeBayesianAnswers,
  storeBayesianDetails,
  storeBayesianScores,
  storeConfirmedConditions,
  storeMLScores,
} from '@/src/lib/medgemma';
import type {
  BayesianConditionTrace,
  BayesianQuestion,
  BayesianQuestionsResult,
  BayesianStagedFollowUp,
  ClarificationQAPair,
  ConditionQuestion,
} from '@/src/lib/medgemma';

type LoadPhase = 'loading' | 'ready' | 'submitting' | 'error';

function conditionLabel(condition: string): string {
  const labels: Record<string, string> = {
    anemia: 'Anaemia',
    iron_deficiency: 'Iron deficiency',
    thyroid: 'Thyroid',
    kidney: 'Kidney function',
    sleep_disorder: 'Sleep disorder',
    liver: 'Liver function',
    prediabetes: 'Prediabetes',
    inflammation: 'Inflammation',
    electrolytes: 'Electrolyte balance',
    hepatitis: 'Hepatitis',
    perimenopause: 'Perimenopause',
  };
  return labels[condition] ?? condition;
}

function AnswerPill({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-4 py-2 text-sm font-medium transition-all duration-150 active:scale-[0.97]',
        selected
          ? 'border-[var(--color-accent)] bg-[var(--color-accent)] text-white shadow-[0_4px_12px_rgba(119,101,244,0.28)]'
          : 'border-[rgba(151,166,210,0.4)] bg-white text-[var(--color-ink)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]',
      ].join(' ')}
    >
      {selected && <span className="mr-1.5 text-xs">✓</span>}
      {label}
    </button>
  );
}

function QuestionBlock({
  tagLabel,
  tagColor,
  question,
  selectedValue,
  onSelect,
}: {
  tagLabel: string;
  tagColor: string;
  question: BayesianQuestion;
  selectedValue: string | undefined;
  onSelect: (val: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span
          className="shrink-0 rounded-full px-3 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em]"
          style={{ backgroundColor: tagColor, color: 'var(--color-ink)' }}
        >
          {tagLabel}
        </span>
        <p className="text-[0.95rem] font-medium leading-[1.45] text-[var(--color-ink)]">
          {question.text}
        </p>
      </div>

      <div className="flex flex-wrap gap-2 pl-1">
        {question.answer_options.map((opt) => (
          <AnswerPill
            key={`${question.id}-${opt.value}`}
            label={opt.label}
            selected={selectedValue === opt.value}
            onClick={() => onSelect(opt.value)}
          />
        ))}
      </div>
    </div>
  );
}

function visibleQuestionsForCondition(
  conditionGroup: ConditionQuestion,
  selectedAnswers: Record<string, string>,
): BayesianQuestion[] {
  const staged = conditionGroup.staged_follow_up;
  if (!staged) return conditionGroup.questions;

  const hiddenIds = new Set(staged.hidden_question_ids);
  const baseQuestions = conditionGroup.questions.filter((question) => !hiddenIds.has(question.id));
  const entryAnswer = selectedAnswers[staged.entry_question_id];
  const shouldExpand = entryAnswer ? staged.continue_on_values.includes(entryAnswer) : false;
  return shouldExpand ? conditionGroup.questions : baseQuestions;
}

function questionCountLabel(
  conditionGroup: ConditionQuestion,
  staged: BayesianStagedFollowUp | null | undefined,
): string {
  if (!staged) return `${conditionGroup.questions.length} questions`;
  const hiddenCount = staged.hidden_question_ids.filter((id) =>
    conditionGroup.questions.some((question) => question.id === id)
  ).length;
  const baseCount = Math.max(conditionGroup.questions.length - hiddenCount, 1);
  const extraCount = conditionGroup.questions.length - baseCount;
  return extraCount > 0 ? `${baseCount} starter + ${extraCount} follow-up` : `${baseCount} questions`;
}

export default function ClarifyPage() {
  const router = useRouter();
  const { answers, hydrated } = useAssessment();

  const [phase, setPhase] = useState<LoadPhase>('loading');
  const [bayesianData, setBayesianData] = useState<BayesianQuestionsResult | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [retryKey, setRetryKey] = useState(0);
  const [currentScreenIndex, setCurrentScreenIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!hydrated) return;

    const cancelled = { current: false };

    const load = async () => {
      try {
        setErrorMessage(null);
        let mlScores = readStoredMLScores() ?? {};
        if (Object.keys(mlScores).length === 0) {
          const { scores, confirmed } = await fetchMLScoresWithTimeout(answers);
          storeMLScores(scores);
          storeConfirmedConditions(confirmed);
          mlScores = scores;
        }
        if (cancelled.current) return;

        const patientSex = answers.gender === '2' ? 'female'
          : answers.gender === '1' ? 'male'
            : undefined;

        const data = await fetchBayesianQuestionsWithTimeout(
          mlScores,
          patientSex as string | undefined,
          answers,
        );
        if (cancelled.current) return;

        if (data.condition_questions.length === 0) {
          router.replace('/processing');
          return;
        }

        setBayesianData(data);
        setCurrentScreenIndex(0);
        setPhase('ready');
      } catch (error) {
        if (!cancelled.current) {
          setErrorMessage(error instanceof Error ? error.message : 'Please try again.');
          setPhase('error');
        }
      }
    };

    void load();
    return () => { cancelled.current = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, retryKey]);

  const conditionQs: ConditionQuestion[] = bayesianData?.condition_questions ?? [];
  const currentCondition = conditionQs[currentScreenIndex];
  const currentQuestions = currentCondition ? visibleQuestionsForCondition(currentCondition, selectedAnswers) : [];
  const isLastScreen = currentScreenIndex === conditionQs.length - 1;
  const currentScreenAnswered = currentQuestions.length > 0
    && currentQuestions.every((q) => q.id in selectedAnswers);
  const allQuestionIds = conditionQs.flatMap((cq) =>
    visibleQuestionsForCondition(cq, selectedAnswers).map((q) => q.id)
  );
  const allAnswered = allQuestionIds.length > 0
    && allQuestionIds.every((id) => id in selectedAnswers);

  const select = (qId: string, val: string) =>
    setSelectedAnswers((prev) => ({ ...prev, [qId]: val }));

  const skipCurrentCondition = () => {
    if (!currentCondition || phase === 'submitting') return;

    setSelectedAnswers((prev) => {
      const next = { ...prev };
      for (const question of currentQuestions) {
        delete next[question.id];
      }
      return next;
    });

    if (isLastScreen) {
      void handleSubmit();
      return;
    }

    setCurrentScreenIndex((index) => Math.min(conditionQs.length - 1, index + 1));
  };

  const handleSubmit = async () => {
    if (!allAnswered) return;
    setPhase('submitting');

    try {
      const mlScores = readStoredMLScores() ?? {};
      const patientSex = answers.gender === '2' ? 'female'
        : answers.gender === '1' ? 'male'
          : undefined;
      const answersByCondition: Record<string, Record<string, string>> = {};

      for (const conditionGroup of conditionQs) {
        for (const question of visibleQuestionsForCondition(conditionGroup, selectedAnswers)) {
          const value = selectedAnswers[question.id];
          if (!value) continue;
          answersByCondition[conditionGroup.condition] ??= {};
          answersByCondition[conditionGroup.condition][question.id] = value;
        }
      }

      const result = await fetchBayesianUpdateWithTimeout(
        mlScores,
        {},
        answersByCondition,
        patientSex as string | undefined,
        answers,
      );

      const qaRecord: ClarificationQAPair[] = conditionQs.flatMap((conditionGroup) =>
        visibleQuestionsForCondition(conditionGroup, selectedAnswers).flatMap((question) => {
          const value = selectedAnswers[question.id];
          if (!value) return [];
          const label = question.answer_options.find((opt) => opt.value === value)?.label ?? value;
          return [{
            group: `${conditionLabel(conditionGroup.condition)} · ${Math.round(conditionGroup.probability * 100)}%`,
            question: question.text,
            answer: label,
          }];
        })
      );

      const questionMeta = Object.fromEntries(
        conditionQs.flatMap((conditionGroup) =>
          conditionGroup.questions.map((question) => [
            question.id,
            {
              condition: conditionGroup.condition,
              text: question.text,
              answers: Object.fromEntries(question.answer_options.map((opt) => [opt.value, opt.label])),
            },
          ])
        )
      ) as Record<string, { condition: string; text: string; answers: Record<string, string> }>;

      const detailRecord = Object.fromEntries(
        Object.entries(result.details ?? {}).map(([condition, detail]) => {
          const trace = detail as BayesianConditionTrace;
          const lrsApplied = Array.isArray(trace?.lrs_applied) ? trace.lrs_applied : [];
          return [
            condition,
            {
              ...trace,
              condition,
              lrs_applied: lrsApplied.map((entry) => ({
                ...entry,
                questionText: questionMeta[entry.question_id]?.text,
                answerLabel: questionMeta[entry.question_id]?.answers?.[entry.answer] ?? entry.answer,
              })),
            },
          ];
        })
      );

      storeBayesianScores(result.posteriorScores);
      storeBayesianDetails(detailRecord);
      storeBayesianAnswers(qaRecord);
      router.push('/processing');
    } catch {
      setPhase('ready');
    }
  };

  if (!hydrated || phase === 'loading') {
    return (
      <div className="phone-frame flex items-center justify-center">
        <p className="text-sm font-medium text-[var(--color-ink-soft)]">
          Scoring your assessment…
        </p>
      </div>
    );
  }

  if (phase === 'error') {
    return (
      <div className="phone-frame flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 px-8 text-center">
          <p className="text-sm font-medium text-[var(--color-ink-soft)]">
            Could not load follow-up questions — please try again.
          </p>
          {errorMessage && (
            <p className="max-w-xs text-xs leading-5 text-[var(--color-ink-soft)]">
              {errorMessage}
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              setBayesianData(null);
              setSelectedAnswers({});
              setCurrentScreenIndex(0);
              setErrorMessage(null);
              setPhase('loading');
              setRetryKey((current) => current + 1);
            }}
            className="rounded-full bg-[#09090f] px-6 py-3 text-sm font-bold text-white"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!currentCondition) {
    return null;
  }

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex-1 overflow-y-auto px-5 py-6">
        <div className="mx-auto flex max-w-lg flex-col gap-5">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <span className="text-[var(--color-ink-soft)]">
              Clarify {currentScreenIndex + 1}/{conditionQs.length}
            </span>
          </div>

          <section className="rounded-[2rem] bg-[var(--color-card)] px-5 py-5 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
                Suspected pattern
              </p>
              <button
                type="button"
                disabled={phase === 'submitting'}
                onClick={skipCurrentCondition}
                className={[
                  'rounded-full border px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] transition-all',
                  phase !== 'submitting'
                    ? 'border-[rgba(151,166,210,0.35)] bg-white text-[var(--color-ink-soft)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]'
                    : 'border-[rgba(151,166,210,0.18)] bg-white/50 text-[rgba(9,9,15,0.34)]',
                ].join(' ')}
              >
                Skip this hypothesis
              </button>
            </div>
            <h1 className="text-[1.75rem] font-bold leading-[1.05] tracking-[-0.05em] text-[var(--color-ink)]">
              {conditionLabel(currentCondition.condition)}
            </h1>
            <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
              We found a signal here. These symptom questions help us verify it before building the report.
            </p>

            <div className="mt-4 flex items-center gap-3">
              <span className="rounded-full bg-[var(--color-lime)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--color-ink)]">
                {Math.round(currentCondition.probability * 100)}% model score
              </span>
              <span className="text-xs font-medium text-[var(--color-ink-soft)]">
                {questionCountLabel(currentCondition, currentCondition.staged_follow_up)}
              </span>
            </div>

            <div className="mt-4 h-2 rounded-full bg-[rgba(151,166,210,0.18)]">
              <div
                className="h-full rounded-full bg-[var(--color-accent)] transition-all duration-300"
                style={{ width: `${((currentScreenIndex + 1) / conditionQs.length) * 100}%` }}
              />
            </div>
          </section>

          <div className="flex flex-col divide-y divide-[rgba(151,166,210,0.18)] rounded-[1.75rem] bg-[var(--color-card)] shadow-[0_8px_24px_rgba(86,98,145,0.10)]">
            {currentQuestions.map((question, index) => (
              <div
                key={question.id}
                className={['px-5 py-4', index === 0 && 'pt-5', index === currentQuestions.length - 1 && 'pb-5']
                  .filter(Boolean)
                  .join(' ')}
              >
                <QuestionBlock
                  tagLabel={`${conditionLabel(currentCondition.condition)} · ${index + 1}`}
                  tagColor="rgba(119,101,244,0.12)"
                  question={question}
                  selectedValue={selectedAnswers[question.id]}
                  onSelect={(val) => select(question.id, val)}
                />
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={currentScreenIndex === 0 || phase === 'submitting'}
              onClick={() => setCurrentScreenIndex((index) => Math.max(0, index - 1))}
              className={[
                'flex-1 rounded-full px-5 py-4 text-base font-bold transition-all',
                currentScreenIndex > 0 && phase !== 'submitting'
                  ? 'bg-white text-[var(--color-ink)] shadow-[0_10px_24px_rgba(86,98,145,0.12)]'
                  : 'bg-white/50 text-[rgba(9,9,15,0.34)]',
              ].join(' ')}
            >
              Back
            </button>

            {isLastScreen ? (
              <button
                type="button"
                disabled={!allAnswered || phase === 'submitting'}
                onClick={() => void handleSubmit()}
                className={[
                  'flex-[1.35] rounded-full px-5 py-4 text-base font-bold transition-all',
                  allAnswered && phase !== 'submitting'
                    ? 'bg-[#09090f] text-white shadow-[0_10px_24px_rgba(9,9,15,0.22)]'
                    : 'bg-white/50 text-[rgba(9,9,15,0.34)]',
                ].join(' ')}
              >
                {phase === 'submitting' ? 'Updating…' : 'Prepare my report'}
              </button>
            ) : (
              <button
                type="button"
                disabled={!currentScreenAnswered || phase === 'submitting'}
                onClick={() => setCurrentScreenIndex((index) => Math.min(conditionQs.length - 1, index + 1))}
                className={[
                  'flex-[1.35] rounded-full px-5 py-4 text-base font-bold transition-all',
                  currentScreenAnswered && phase !== 'submitting'
                    ? 'bg-[#09090f] text-white shadow-[0_10px_24px_rgba(9,9,15,0.22)]'
                    : 'bg-white/50 text-[rgba(9,9,15,0.34)]',
                ].join(' ')}
              >
                Next condition
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
