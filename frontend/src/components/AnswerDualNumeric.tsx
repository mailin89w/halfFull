'use client';

interface Field {
  value: string;
  label: string;
  sub_type?: 'binary' | 'numeric';
  help_text?: string;
  unit?: string;
  min?: number;
  max?: number;
}

interface Props {
  fields: Field[];
  value: Record<string, string> | undefined;
  onChange: (val: Record<string, string>) => void;
  min?: number;
  max?: number;
  errors?: Record<string, string>;
}

export function AnswerDualNumeric({
  fields,
  value = {},
  onChange,
  errors = {},
}: Props) {
  const handleChange = (key: string, raw: string) => {
    onChange({ ...value, [key]: raw });
  };

  return (
    <div className="flex flex-col gap-4">
      {fields.map((field) => (
        <div key={field.value} className="flex flex-col gap-1.5">
          <div>
            <span className="text-sm font-medium text-[var(--color-ink)]">{field.label}</span>
            {field.help_text && (
              <span className="ml-1.5 text-xs text-[var(--color-ink-soft)]">{field.help_text}</span>
            )}
          </div>

          {field.sub_type === 'binary' ? (
            <div className="flex gap-2">
              {[{ val: '1', label: 'Yes' }, { val: '2', label: 'No' }].map(({ val, label }) => {
                const selected = value[field.value] === val;
                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => handleChange(field.value, val)}
                    className={[
                      'flex-1 rounded-[1.35rem] border px-4 py-2.5 text-sm font-medium transition-colors',
                      selected
                        ? 'border-[var(--color-accent)] bg-[var(--color-accent)] text-white'
                        : 'border-[rgba(151,166,210,0.4)] bg-white text-[var(--color-ink)] hover:border-[var(--color-accent)]',
                    ].join(' ')}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="relative">
              <input
                type="number"
                inputMode="decimal"
                value={value[field.value] ?? ''}
                onChange={(e) => handleChange(field.value, e.target.value)}
                placeholder="0"
                className={[
                  'w-full rounded-[1.35rem] border bg-white px-4 py-3 pr-16',
                  errors[field.value]
                    ? 'border-[rgba(179,67,67,0.45)] text-[var(--color-ink)]'
                    : 'border-[rgba(151,166,210,0.28)] text-[var(--color-ink)]',
                  'text-base placeholder-[var(--color-ink-soft)]',
                  'focus:border-[var(--color-accent)] focus:outline-none transition-colors',
                  '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none',
                ].join(' ')}
              />
              {field.unit && (
                <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-sm text-[var(--color-ink-soft)]">
                  {field.unit}
                </span>
              )}
              {errors[field.value] && (
                <p className="mt-2 text-sm text-[#b34343]">{errors[field.value]}</p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
