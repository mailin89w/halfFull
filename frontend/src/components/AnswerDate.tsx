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
        'w-full px-4 py-4 rounded-2xl',
        'border-2 border-[#A2B6CB]/40 bg-white',
        'text-[#254662] text-base',
        'focus:outline-none focus:border-[#EFB973] transition-colors',
      ].join(' ')}
    />
  );
}
