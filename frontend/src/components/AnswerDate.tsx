'use client';

interface Props {
  value: string | undefined;
  onChange: (val: string) => void;
}

export function AnswerDate({ value = '', onChange }: Props) {
  const today = new Date().toISOString().split('T')[0];

  return (
    <input
      type="date"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      max={today}
      className={[
        'w-full rounded-[1.35rem] border bg-white px-4 py-4',
        'border-[rgba(151,166,210,0.28)] text-[var(--color-ink)] text-base',
        'focus:border-[var(--color-accent)] focus:outline-none transition-colors',
      ].join(' ')}
    />
  );
}
