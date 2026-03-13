'use client';

interface Props {
  value: string | undefined;
  onChange: (val: string) => void;
  placeholder?: string;
  rows?: number;
}

export function AnswerFreeText({
  value = '',
  onChange,
  placeholder = 'Type your answer here…',
  rows = 4,
}: Props) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className={[
        'w-full rounded-[1.35rem] border bg-white px-4 py-3',
        'border-[rgba(151,166,210,0.28)] text-[var(--color-ink)] text-base placeholder-[var(--color-ink-soft)]',
        'focus:border-[var(--color-accent)] focus:outline-none transition-colors',
        'resize-none',
      ].join(' ')}
    />
  );
}
