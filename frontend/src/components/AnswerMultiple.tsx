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
              'w-full px-5 py-4 rounded-2xl text-left text-base font-medium',
              'border-2 transition-all duration-150 flex items-center gap-3 active:scale-[0.98]',
              selected
                ? 'border-[#EFB973] bg-[#EFB973]/15 text-[#254662]'
                : 'border-[#A2B6CB]/40 bg-white text-[#254662] hover:border-[#EFB973]/60 hover:bg-[#EFB973]/5',
            ].join(' ')}
          >
            <span
              className={[
                'w-5 h-5 rounded flex-shrink-0 border-2 flex items-center justify-center transition-colors',
                selected ? 'bg-[#EFB973] border-[#EFB973]' : 'border-[#A2B6CB] bg-white',
              ].join(' ')}
            >
              {selected && (
                <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
                  <path
                    d="M1 4L4 7L10 1"
                    stroke="#254662"
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
        <p className="text-xs text-[#A2B6CB] text-center mt-1">
          {value.length} selected
        </p>
      )}
    </div>
  );
}
