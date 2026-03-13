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
                'aspect-square rounded-2xl text-sm font-bold',
                'border transition-all duration-150 active:scale-[0.92]',
                selected
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent)] text-white shadow-[0_10px_18px_rgba(119,101,244,0.2)]'
                  : 'border-[rgba(151,166,210,0.28)] bg-white text-[var(--color-ink)]',
              ].join(' ')}
            >
              {n}
            </button>
          );
        })}
      </div>
      <div className="flex justify-between px-0.5 text-xs text-[var(--color-ink-soft)]">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}
