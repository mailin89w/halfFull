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
              'w-full px-5 py-4 rounded-2xl text-left text-base font-medium',
              'border-2 transition-all duration-150 active:scale-[0.98]',
              selected
                ? 'border-[#EFB973] bg-[#EFB973]/15 text-[#254662]'
                : 'border-[#A2B6CB]/40 bg-white text-[#254662] hover:border-[#EFB973]/60 hover:bg-[#EFB973]/5',
            ].join(' ')}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
