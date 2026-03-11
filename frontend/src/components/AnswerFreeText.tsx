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
        'w-full px-4 py-3 rounded-2xl',
        'border-2 border-[#A2B6CB]/40 bg-white',
        'text-[#254662] text-base placeholder-[#A2B6CB]',
        'focus:outline-none focus:border-[#EFB973] transition-colors',
        'resize-none',
      ].join(' ')}
    />
  );
}
