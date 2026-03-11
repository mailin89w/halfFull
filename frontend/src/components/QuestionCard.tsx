'use client';

import type { Question } from '@/src/lib/questions';
import { MODULE_COLORS, MODULE_LABELS } from '@/src/lib/questions';
import { AnswerSingle } from './AnswerSingle';
import { AnswerMultiple } from './AnswerMultiple';
import { AnswerScale } from './AnswerScale';
import { AnswerFreeText } from './AnswerFreeText';
import { AnswerDate } from './AnswerDate';
import { AnswerFileUpload } from './AnswerFileUpload';

interface Props {
  question: Question;
  value: unknown;
  onChange: (val: unknown) => void;
}

// Derive a display label from the question id, e.g. "q0.0" → "Q0.0"
function idToLabel(id: string): string {
  return id.replace(/^q/, 'Q');
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

      // Multi-select checkboxes
      case 'multi_select':
        return (
          <AnswerMultiple
            options={question.options}
            value={value as string[] | undefined}
            onChange={(v) => onChange(v)}
          />
        );

      // 1–10 numeric scale
      case 'numeric':
        return (
          <AnswerScale
            value={value as number | undefined}
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
            value={value as string | undefined}
            onChange={(v) => onChange(v)}
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
    <div className="bg-white rounded-3xl p-6 shadow-[0_4px_24px_rgba(37,70,98,0.08)] flex flex-col gap-5">
      {/* Module badge + question id label */}
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="px-3 py-1 rounded-full text-xs font-semibold text-[#254662]"
          style={{ backgroundColor: `${accentColor}33` }}
        >
          {moduleLabel}
        </span>
        <span className="text-xs text-[#A2B6CB] font-medium">{idToLabel(question.id)}</span>
      </div>

      {/* Question text */}
      <h2 className="text-xl font-semibold text-[#254662] leading-snug">
        {question.text}
      </h2>

      {/* Help text */}
      {question.help_text && (
        <p className="text-sm text-[#A2B6CB] -mt-2 leading-relaxed">{question.help_text}</p>
      )}

      {/* Answer input */}
      {renderInput()}
    </div>
  );
}
