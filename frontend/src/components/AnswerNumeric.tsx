'use client';

interface Props {
  value: string | undefined;
  onChange: (val: string) => void;
  placeholder?: string;
}

export function AnswerNumeric({ value = '', onChange, placeholder = 'Enter a number' }: Props) {
  return (
    <input
      type="number"
      inputMode="decimal"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={[
        'w-full rounded-[1.35rem] border bg-white px-4 py-3',
        'border-[rgba(151,166,210,0.28)] text-[var(--color-ink)] text-base placeholder-[var(--color-ink-soft)]',
        'focus:border-[var(--color-accent)] focus:outline-none transition-colors',
        '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none',
      ].join(' ')}
    />
  );
}
