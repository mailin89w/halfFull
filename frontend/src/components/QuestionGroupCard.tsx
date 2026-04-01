'use client';

import type { Question } from '@/src/lib/questions';
import { MODULE_COLORS, MODULE_LABELS, getQuestionDisplayText } from '@/src/lib/questions';
import { AnswerSingle } from './AnswerSingle';
import { AnswerNumeric } from './AnswerNumeric';

interface Props {
  questions: Question[];
  answers: Record<string, unknown>;
  onAnswer: (questionId: string, val: unknown) => void;
  errors?: Record<string, string | Record<string, string>>;
}

function renderInput(
  question: Question,
  value: unknown,
  onChange: (val: unknown) => void,
  error?: string | Record<string, string>
) {
  switch (question.type) {
    case 'binary':
    case 'categorical':
    case 'ordinal':
      return (
        <AnswerSingle
          options={question.options}
          value={value as string | undefined}
          onChange={onChange}
          layout={question.answer_layout}
        />
      );
    case 'numeric':
      return (
        <AnswerNumeric
          value={value as string | undefined}
          onChange={onChange}
          min={question.validation?.min}
          max={question.validation?.max}
          error={typeof error === 'string' ? error : undefined}
          unit={question.options[0]?.unit}
        />
      );
    default:
      return null;
  }
}

export function QuestionGroupCard({ questions, answers, onAnswer, errors = {} }: Props) {
  if (questions.length === 0) return null;

  const first = questions[0];
  const accentColor = MODULE_COLORS[first.module] ?? '#A2B6CB';
  const moduleLabel = MODULE_LABELS[first.module] ?? first.moduleTitle;
  const leadQuestionIds = new Set([
    'kiq005___how_often_have_urinary_leakage?',
    'med_count',
    'smq020___smoked_at_least_100_cigarettes_in_life',
  ]);

  return (
    <div className="section-card flex flex-col gap-6 p-6">
      {/* Module tag */}
      <span
        className="pill-tag text-[var(--color-ink)] self-start"
        style={{ backgroundColor: `${accentColor}44` }}
      >
        {moduleLabel}
      </span>

      {/* Individual questions */}
      {questions.map((q) => (
        <div key={q.id} className="flex flex-col gap-3">
          {leadQuestionIds.has(q.id) ? (
            <h2 className="text-[1.75rem] font-bold leading-[1] tracking-[-0.05em] text-[var(--color-ink)] sm:text-[2rem]">
              {getQuestionDisplayText(q, answers)}
            </h2>
          ) : (
            <h3 className="text-[1.15rem] font-semibold leading-snug tracking-[-0.03em] text-[var(--color-ink)]">
              {getQuestionDisplayText(q, answers)}
            </h3>
          )}
          {q.help_text && (
            <p className="-mt-1 max-w-[30rem] text-sm leading-6 text-[var(--color-ink-soft)]">
              {q.help_text}
            </p>
          )}
          {renderInput(q, answers[q.id], (val) => onAnswer(q.id, val), errors[q.id])}
        </div>
      ))}
    </div>
  );
}
