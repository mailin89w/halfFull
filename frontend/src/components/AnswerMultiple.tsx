'use client';

import type { QuestionOption } from '@/src/lib/questions';

interface Props {
  options: QuestionOption[];
  value: string[] | undefined;
  onChange: (val: string[]) => void;
}

export function AnswerMultiple({ options, value = [], onChange }: Props) {
  const toggle = (optionValue: string) => {
    // Values ending in "_none" act as the exclusive "None of the above" option
    const isNoneOption = optionValue.endsWith('_none');
    if (isNoneOption) {
      onChange(value.includes(optionValue) ? [] : [optionValue]);
      return;
    }
    // Remove any existing none-selections when picking a real option
    const withoutNone = value.filter((v) => !v.endsWith('_none'));
    if (withoutNone.includes(optionValue)) {
      onChange(withoutNone.filter((v) => v !== optionValue));
    } else {
      onChange([...withoutNone, optionValue]);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {options.map((option) => {
        const selected = value.includes(option.value);
        return (
          <button
            key={option.value}
            onClick={() => toggle(option.value)}
            className={[
              'flex w-full items-center gap-3 rounded-[1.35rem] border px-5 py-4 text-left text-base transition-all duration-150 active:scale-[0.98]',
              selected
                ? 'border-[rgba(119,101,244,0.2)] bg-[var(--color-accent-soft)] text-[var(--color-ink)] shadow-[0_10px_18px_rgba(119,101,244,0.16)]'
                : 'border-[rgba(151,166,210,0.28)] bg-white text-[var(--color-ink)]',
            ].join(' ')}
          >
            <span
              className={[
                'flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md border transition-colors',
                selected
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent)]'
                  : 'border-[rgba(9,9,15,0.18)] bg-white',
              ].join(' ')}
            >
              {selected && (
                <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
                  <path
                    d="M1 4L4 7L10 1"
                    stroke="#fff"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </span>
            {option.label}
          </button>
        );
      })}
      {value.length > 1 && (
        <p className="mt-1 text-center text-xs text-[var(--color-ink-soft)]">
          {value.length} selected
        </p>
      )}
    </div>
  );
}
