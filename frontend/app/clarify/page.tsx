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
  storeBayesianScores,
  storeMLScores,
} from '@/src/lib/medgemma';
import type {
  BayesianQuestionsResult,
  ClarificationQAPair,
  ConditionQuestion,
  ConfounderQuestion,
} from '@/src/lib/medgemma';

type LoadPhase = 'loading' | 'ready' | 'submitting' | 'error';

// ── Helpers ───────────────────────────────────────────────────────────────────

function conditionLabel(condition: string): string {
  const labels: Record<string, string> = {
    anemia:           'Anaemia',
    iron_deficiency:  'Iron deficiency',
    thyroid:          'Thyroid',
    kidney:           'Kidney function',
    sleep_disorder:   'Sleep disorder',
    liver:            'Liver function',
    prediabetes:      'Prediabetes',
    inflammation:     'Inflammation',
    electrolytes:     'Electrolyte balance',
    hepatitis:        'Hepatitis',
    perimenopause:    'Perimenopause',
    depression:       'Mood',
    anxiety:          'Anxiety',
  };
  return labels[condition] ?? condition;
}

// ── Pill answer button ────────────────────────────────────────────────────────

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

// ── Shared question block ─────────────────────────────────────────────────────

function QuestionBlock({
  tagLabel,
  tagColor,
  questionText,
  questionId,
  options,
  selectedValue,
  onSelect,
}: {
  tagLabel: string;
  tagColor: string;
  questionText: string;
  questionId: string;
  options: { value: string; label: string }[];
  selectedValue: string | undefined;
  onSelect: (val: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {/* Tag + question */}
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span
          className="shrink-0 rounded-full px-3 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em]"
          style={{ backgroundColor: tagColor, color: 'var(--color-ink)' }}
        >
          {tagLabel}
        </span>
        <p className="text-[0.95rem] font-medium leading-[1.45] text-[var(--color-ink)]">
          {questionText}
        </p>
      </div>

      {/* Pill answers */}
      <div className="flex flex-wrap gap-2 pl-1">
        {options.map((opt) => (
          <AnswerPill
            key={`${questionId}-${opt.value}`}
            label={opt.label}
            selected={selectedValue === opt.value}
            onClick={() => onSelect(opt.value)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ClarifyPage() {
  const router  = useRouter();
  const { answers, hydrated } = useAssessment();

  const [phase,           setPhase]           = useState<LoadPhase>('loading');
  const [bayesianData,    setBayesianData]    = useState<BayesianQuestionsResult | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [retryKey,        setRetryKey]        = useState(0);

  // ── Load ML scores → Bayesian questions ──────────────────────────────────
  useEffect(() => {
    if (!hydrated) return;

    const cancelled = { current: false };

    const load = async () => {
      try {
        // ML scoring happens here — after quiz+labs are submitted
        let mlScores = readStoredMLScores() ?? {};
        if (Object.keys(mlScores).length === 0) {
          mlScores = await fetchMLScoresWithTimeout(answers);
          storeMLScores(mlScores);
        }
        if (cancelled.current) return;

        const patientSex = answers.gender === '2' ? 'female'
                         : answers.gender === '1' ? 'male'
                         : undefined;

        const data = await fetchBayesianQuestionsWithTimeout(mlScores, patientSex as string | undefined);
        if (cancelled.current) return;

        // No conditions cleared the threshold — skip straight to processing
        if (data.condition_questions.length === 0) {
          router.replace('/processing');
          return;
        }

        setBayesianData(data);
        setPhase('ready');
      } catch {
        if (!cancelled.current) setPhase('error');
      }
    };

    void load();
    return () => { cancelled.current = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, retryKey]);

  // ── Derived state ─────────────────────────────────────────────────────────
  const confounderQs: ConfounderQuestion[] = bayesianData?.confounder_questions ?? [];
  const conditionQs:  ConditionQuestion[]  = bayesianData?.condition_questions  ?? [];

  const allQuestionIds = [
    ...confounderQs.map((q) => q.id),
    ...conditionQs.map((cq) => cq.question.id),
  ];
  const allAnswered = allQuestionIds.length > 0
    && allQuestionIds.every((id) => id in selectedAnswers);

  const select = (qId: string, val: string) =>
    setSelectedAnswers((prev) => ({ ...prev, [qId]: val }));

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!allAnswered || !bayesianData) return;
    setPhase('submitting');

    try {
      const mlScores   = readStoredMLScores() ?? {};
      const patientSex = answers.gender === '2' ? 'female'
                       : answers.gender === '1' ? 'male'
                       : undefined;

      const confounderIds = new Set(confounderQs.map((q) => q.id));
      const confounderAnswers: Record<string, number> = {};
      const answersByCondition: Record<string, Record<string, string>> = {};

      for (const [qId, value] of Object.entries(selectedAnswers)) {
        if (confounderIds.has(qId)) {
          confounderAnswers[qId] = Number(value);
        } else {
          const owner = conditionQs.find((cq) => cq.question.id === qId);
          if (owner) {
            answersByCondition[owner.condition] ??= {};
            answersByCondition[owner.condition][qId] = value;
          }
        }
      }

      const result = await fetchBayesianUpdateWithTimeout(
        mlScores,
        confounderAnswers,
        answersByCondition,
        patientSex as string | undefined,
      );

      // Build human-readable Q&A record for MedGemma prompt
      const qaRecord: ClarificationQAPair[] = [
        ...confounderQs.map((q) => {
          const val = selectedAnswers[q.id];
          const label = q.answer_options.find((o) => String(o.value) === val)?.label ?? val;
          return { group: conditionLabel(q.confounder), question: q.text, answer: label };
        }),
        ...conditionQs.map((cq) => {
          const q   = cq.question;
          const val = selectedAnswers[q.id];
          const label = q.answer_options.find((o) => o.value === val)?.label ?? val;
          return {
            group:    `${conditionLabel(cq.condition)} · ${Math.round(cq.probability * 100)}%`,
            question: q.text,
            answer:   label,
          };
        }),
      ];

      storeBayesianScores(result.posteriorScores);
      storeBayesianAnswers(qaRecord);
      router.push('/processing');
    } catch {
      setPhase('ready');
    }
  };

  // ── Loading / error states ────────────────────────────────────────────────

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
          <button
            type="button"
            onClick={() => {
              setBayesianData(null);
              setSelectedAnswers({});
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

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex-1 overflow-y-auto px-5 py-6">
        <div className="mx-auto flex max-w-lg flex-col gap-5">

          {/* Header */}
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <span className="text-[var(--color-ink-soft)]">Clarify</span>
          </div>

          {/* Hero */}
          <section className="rounded-[2rem] bg-[var(--color-card)] px-5 py-5 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
              A few more details
            </p>
            <h1 className="text-[1.75rem] font-bold leading-[1.05] tracking-[-0.05em] text-[var(--color-ink)]">
              Help us sharpen the picture
            </h1>
            {/* Flagged condition pills */}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {conditionQs.map((cq) => (
                <span
                  key={cq.condition}
                  className="rounded-full bg-[var(--color-lime)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--color-ink)]"
                >
                  {conditionLabel(cq.condition)} · {Math.round(cq.probability * 100)}%
                </span>
              ))}
            </div>
          </section>

          {/* All questions — single card with dividers */}
          <div className="flex flex-col divide-y divide-[rgba(151,166,210,0.18)] rounded-[1.75rem] bg-[var(--color-card)] shadow-[0_8px_24px_rgba(86,98,145,0.10)]">

            {/* Confounder questions (PHQ-2 / GAD-2) */}
            {confounderQs.map((q, i) => (
              <div
                key={q.id}
                className={['px-5 py-4', i === 0 && 'pt-5'].filter(Boolean).join(' ')}
              >
                <QuestionBlock
                  tagLabel={conditionLabel(q.confounder)}
                  tagColor="rgba(151,166,210,0.22)"
                  questionText={q.text}
                  questionId={q.id}
                  options={q.answer_options.map((o) => ({
                    value: String(o.value),
                    label: o.label,
                  }))}
                  selectedValue={selectedAnswers[q.id]}
                  onSelect={(val) => select(q.id, val)}
                />
              </div>
            ))}

            {/* Condition-specific questions */}
            {conditionQs.map((cq, i) => {
              const q    = cq.question;
              const isLast  = i === conditionQs.length - 1;
              const isFirst = confounderQs.length === 0 && i === 0;
              return (
                <div
                  key={q.id}
                  className={['px-5 py-4', isFirst && 'pt-5', isLast && 'pb-5']
                    .filter(Boolean)
                    .join(' ')}
                >
                  <QuestionBlock
                    tagLabel={`${conditionLabel(cq.condition)} · ${Math.round(cq.probability * 100)}%`}
                    tagColor="rgba(119,101,244,0.12)"
                    questionText={q.text}
                    questionId={q.id}
                    options={q.answer_options}
                    selectedValue={selectedAnswers[q.id]}
                    onSelect={(val) => select(q.id, val)}
                  />
                </div>
              );
            })}

          </div>

          {/* Submit */}
          <button
            type="button"
            disabled={!allAnswered || phase === 'submitting'}
            onClick={() => void handleSubmit()}
            className={[
              'w-full rounded-full px-5 py-4 text-base font-bold transition-all',
              allAnswered && phase !== 'submitting'
                ? 'bg-[#09090f] text-white shadow-[0_10px_24px_rgba(9,9,15,0.22)]'
                : 'bg-white/50 text-[rgba(9,9,15,0.34)]',
            ].join(' ')}
          >
            {phase === 'submitting' ? 'Updating…' : 'Prepare my report'}
          </button>

        </div>
      </main>
    </div>
  );
}
