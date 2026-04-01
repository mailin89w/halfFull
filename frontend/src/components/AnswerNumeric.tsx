'use client';

interface Props {
  value: string | undefined;
  onChange: (val: string) => void;
  placeholder?: string;
  min?: number;
  max?: number;
  error?: string;
  unit?: string;
}

export function AnswerNumeric({
  value = '',
  onChange,
  placeholder = 'Enter a number',
  min,
  max,
  error,
  unit,
}: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <input
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={[
            'w-full rounded-[1.35rem] border bg-white px-4 py-3',
            unit ? 'pr-16' : '',
            error
              ? 'border-[rgba(179,67,67,0.45)] text-[var(--color-ink)]'
              : 'border-[rgba(151,166,210,0.28)] text-[var(--color-ink)]',
            'text-base placeholder-[var(--color-ink-soft)]',
            'focus:border-[var(--color-accent)] focus:outline-none transition-colors',
            '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none',
          ].join(' ')}
        />
        {unit && (
          <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-sm text-[var(--color-ink-soft)]">
            {unit}
          </span>
        )}
      </div>
      {error && <p className="text-sm text-[#b34343]">{error}</p>}
    </div>
  );
}
