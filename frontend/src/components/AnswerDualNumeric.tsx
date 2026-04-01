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
  labelClassName?: string;
  helpTextClassName?: string;
  binaryLayout?: 'stacked' | 'inline';
  stackHelpText?: boolean;
}

export function AnswerDualNumeric({
  fields,
  value = {},
  onChange,
  errors = {},
  labelClassName = 'text-sm font-medium text-[var(--color-ink)]',
  helpTextClassName = 'ml-1.5 text-xs text-[var(--color-ink-soft)]',
  binaryLayout = 'inline',
  stackHelpText = false,
}: Props) {
  const handleChange = (key: string, raw: string) => {
    onChange({ ...value, [key]: raw });
  };

  return (
    <div className="flex flex-col gap-4">
      {fields.map((field) => (
        <div key={field.value} className="flex flex-col gap-1.5">
          <div>
            <span className={labelClassName}>{field.label}</span>
            {field.help_text && !stackHelpText && (
              <span className={helpTextClassName}>{field.help_text}</span>
            )}
            {field.help_text && stackHelpText && (
              <p className={helpTextClassName}>{field.help_text}</p>
            )}
          </div>

          {field.sub_type === 'binary' ? (
            <div className={binaryLayout === 'stacked' ? 'flex flex-col gap-3' : 'flex gap-2'}>
              {[{ val: '1', label: 'Yes' }, { val: '2', label: 'No' }].map(({ val, label }) => {
                const selected = value[field.value] === val;
                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => handleChange(field.value, val)}
                    className={[
                      'rounded-[1.35rem] border px-5 py-4 transition-all duration-150 active:scale-[0.98]',
                      binaryLayout === 'stacked' ? 'w-full text-left text-base' : 'flex-1 text-sm font-medium',
                      selected
                        ? 'border-[rgba(119,101,244,0.2)] bg-[var(--color-accent-soft)] text-[var(--color-ink)] shadow-[0_10px_18px_rgba(119,101,244,0.16)]'
                        : 'border-[rgba(151,166,210,0.28)] bg-white text-[var(--color-ink)]',
                    ].join(' ')}
                  >
                    <div className={binaryLayout === 'stacked' ? 'flex items-center justify-between gap-4' : 'flex items-center justify-center gap-3'}>
                      <span className={binaryLayout === 'stacked' ? 'font-medium' : ''}>{label}</span>
                      <span
                        className={[
                          'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold',
                          selected
                            ? 'border-[var(--color-accent)] bg-[var(--color-accent)] text-white'
                            : 'border-[rgba(9,9,15,0.15)] text-transparent',
                        ].join(' ')}
                      >
                        ✓
                      </span>
                    </div>
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
