'use client';

interface Props {
  value: number | undefined;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
  lowLabel?: string;
  highLabel?: string;
}

export function AnswerScale({
  value,
  onChange,
  min = 1,
  max = 10,
  lowLabel = 'Very poor',
  highLabel = 'Excellent',
}: Props) {
  const ticks = Array.from({ length: max - min + 1 }, (_, i) => i + min);

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${ticks.length}, 1fr)` }}>
        {ticks.map((n) => {
          const selected = value === n;
          return (
            <button
              key={n}
              onClick={() => onChange(n)}
              className={[
                'aspect-square rounded-xl text-sm font-semibold',
                'border-2 transition-all duration-150 active:scale-[0.92]',
                selected
                  ? 'border-[#EFB973] bg-[#EFB973] text-[#254662]'
                  : 'border-[#A2B6CB]/40 bg-white text-[#254662] hover:border-[#EFB973]/60 hover:bg-[#EFB973]/5',
              ].join(' ')}
            >
              {n}
            </button>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-[#A2B6CB] px-0.5">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}
