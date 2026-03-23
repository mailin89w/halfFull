'use client';

import type { Question } from '@/src/lib/questions';
import { MODULE_COLORS, MODULE_LABELS } from '@/src/lib/questions';
import type { LabUploadAnswer } from '@/src/lib/types';
import { AnswerSingle } from './AnswerSingle';
import { AnswerMultiple } from './AnswerMultiple';
import { AnswerNumeric } from './AnswerNumeric';
import { AnswerFreeText } from './AnswerFreeText';
import { AnswerDate } from './AnswerDate';
import { AnswerFileUpload } from './AnswerFileUpload';
import { AnswerDualNumeric } from './AnswerDualNumeric';

interface Props {
  question: Question;
  value: unknown;
  onChange: (val: unknown) => void;
}

// Derive a short display label from the question id.
// Old-style: "q0.0" → "Q0.0". NHANES-style: show nothing (module tag is enough).
function idToLabel(id: string): string {
  if (/^q\d/.test(id)) return id.replace(/^q/, 'Q');
  return '';
}

export function QuestionCard({ question, value, onChange }: Props) {
  const accentColor = MODULE_COLORS[question.module] ?? '#A2B6CB';
  const moduleLabel = MODULE_LABELS[question.module] ?? question.moduleTitle;

  const renderInput = () => {
    switch (question.type) {
      // Single-select types (binary, categorical, ordinal all render as button list)
      case 'binary':
      case 'categorical':
      case 'ordinal':
        return (
          <AnswerSingle
            options={question.options}
            value={value as string | undefined}
            onChange={(v) => onChange(v)}
          />
        );

      // Multi-select (pills layout for large option sets)
      case 'multi_select':
        return (
          <AnswerMultiple
            options={question.options}
            value={value as string[] | undefined}
            onChange={(v) => onChange(v)}
            layout={question.options.length > 5 ? 'pills' : 'list'}
          />
        );

      case 'numeric':
        return (
          <AnswerNumeric
            value={value as string | undefined}
            onChange={(v) => onChange(v)}
          />
        );

      case 'dual_numeric':
        return (
          <AnswerDualNumeric
            fields={question.options}
            value={value as Record<string, string> | undefined}
            onChange={(v) => onChange(v)}
          />
        );

      case 'date':
        return (
          <AnswerDate
            value={value as string | undefined}
            onChange={(v) => onChange(v)}
          />
        );

      case 'file_upload':
        return (
          <AnswerFileUpload
            value={value as LabUploadAnswer | undefined}
            onChange={(v) => onChange(v)}
          />
        );

      case 'free_text':
        return (
          <AnswerFreeText
            value={value as string | undefined}
            onChange={(v) => onChange(v)}
            placeholder="Describe any other symptoms — brain fog, palpitations, hair loss, temperature sensitivity…"
            rows={5}
          />
        );

      default:
        return (
          <AnswerFreeText
            value={value as string | undefined}
            onChange={(v) => onChange(v)}
          />
        );
    }
  };

  return (
    <div className="section-card flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <span
          className="pill-tag text-[var(--color-ink)]"
          style={{ backgroundColor: `${accentColor}44` }}
        >
          {moduleLabel}
        </span>
        {idToLabel(question.id) && (
          <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
            {idToLabel(question.id)}
          </span>
        )}
      </div>

      <h2 className="text-[1.9rem] font-bold leading-[1] tracking-[-0.05em] text-[var(--color-ink)] sm:text-[2.2rem]">
        {question.text}
      </h2>

      {question.help_text && (
        <p className="-mt-3 max-w-[30rem] text-sm leading-6 text-[var(--color-ink-soft)]">
          {question.help_text}
        </p>
      )}

      {renderInput()}
    </div>
  );
}
