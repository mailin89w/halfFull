'use client';

import type { QuestionOption } from '@/src/lib/questions';

interface Props {
  options: QuestionOption[];
  value: string | undefined;
  onChange: (val: string) => void;
}

export function AnswerSingle({ options, value, onChange }: Props) {
  return (
    <div className="flex flex-col gap-3">
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={[
              'w-full rounded-[1.35rem] border px-5 py-4 text-left text-base transition-all duration-150 active:scale-[0.98]',
              selected
                ? 'border-[rgba(119,101,244,0.2)] bg-[var(--color-accent-soft)] text-[var(--color-ink)] shadow-[0_10px_18px_rgba(119,101,244,0.16)]'
                : 'border-[rgba(151,166,210,0.28)] bg-white text-[var(--color-ink)]',
            ].join(' ')}
          >
            <div className="flex items-center justify-between gap-4">
              <span className="font-medium">{option.label}</span>
              <span
                className={[
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold',
                  selected
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent)] text-white'
                    : 'border-[rgba(9,9,15,0.15)] text-transparent',
                ].join(' ')}
              >
                ✓
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
