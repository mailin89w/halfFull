'use client';

import { useState } from 'react';
import type { Diagnosis, SignalStrength } from '@/src/lib/mockResults';

interface Props {
  diagnosis: Diagnosis;
  rank: number;
  personalNote?: string;
}

const SIGNAL_CONFIG: Record<
  SignalStrength,
  { label: string; dotColor: string; pillBg: string; pillText: string }
> = {
  strong: {
    label: 'Strong signal',
    dotColor: 'bg-[var(--color-accent)]',
    pillBg: 'bg-[var(--color-accent-soft)]',
    pillText: 'text-[var(--color-ink)]',
  },
  moderate: {
    label: 'Moderate signal',
    dotColor: 'bg-[var(--color-lime)]',
    pillBg: 'bg-[rgba(215,240,104,0.3)]',
    pillText: 'text-[var(--color-ink)]',
  },
  investigating: {
    label: 'Worth investigating',
    dotColor: 'bg-[#9ea9d3]',
    pillBg: 'bg-[rgba(158,169,211,0.25)]',
    pillText: 'text-[var(--color-ink)]',
  },
};

export function DiagnosisCard({ diagnosis, rank, personalNote }: Props) {
  const [open, setOpen] = useState(false);
  const cfg = SIGNAL_CONFIG[diagnosis.signal];

  return (
    <div
      className={[
        'overflow-hidden rounded-[1.8rem] border transition-all duration-200',
        open ? 'border-[rgba(119,101,244,0.4)] shadow-[0_16px_30px_rgba(119,101,244,0.1)]' : 'border-[rgba(151,166,210,0.25)]',
      ].join(' ')}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-4 bg-[var(--color-card)] px-5 py-4 text-left transition-colors"
      >
        <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#09090f] text-xs font-bold text-white">
          {rank}
        </span>

        <span className="text-2xl flex-shrink-0">{diagnosis.emoji}</span>

        <div className="flex-1 min-w-0">
          <p className="text-base font-bold leading-snug tracking-[-0.03em] text-[var(--color-ink)]">{diagnosis.title}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dotColor}`} />
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cfg.pillBg} ${cfg.pillText}`}>
              {cfg.label}
            </span>
          </div>
        </div>

        <svg
          width="18"
          height="18"
          viewBox="0 0 18 18"
          fill="none"
          className={`flex-shrink-0 text-[var(--color-ink-soft)] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M4.5 6.75L9 11.25L13.5 6.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="flex flex-col gap-5 border-t border-[rgba(151,166,210,0.18)] bg-[var(--color-card)] px-5 pb-5 pt-1">
          {personalNote && (
            <div className="flex gap-2.5 rounded-2xl border border-[rgba(119,101,244,0.12)] bg-[var(--color-accent-soft)] px-4 py-3">
              <span className="text-base flex-shrink-0">✨</span>
              <p className="text-xs leading-relaxed text-[var(--color-ink)]">{personalNote}</p>
            </div>
          )}

          <p className="text-sm leading-6 text-[var(--color-ink-soft)]">{diagnosis.description}</p>

          <div>
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-ink)]">
              Tests to request from your GP
            </h4>
            <div className="flex flex-col gap-2.5">
              {diagnosis.tests.map((test) => (
                <div key={test.name} className="flex items-start gap-2.5">
                  <span className="mt-0.5 text-[var(--color-accent)] font-bold text-xs flex-shrink-0">•</span>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-[var(--color-ink)]">{test.name}</span>
                      {test.mustRequest && (
                        <span className="rounded-full bg-[rgba(215,240,104,0.45)] px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap text-[var(--color-ink)]">
                          request explicitly
                        </span>
                      )}
                    </div>
                    {test.note && (
                      <p className="mt-0.5 text-xs leading-snug text-[var(--color-ink-soft)]">{test.note}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1 rounded-2xl border border-[rgba(119,101,244,0.14)] bg-white p-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-ink)]">Recovery outlook</span>
            </div>
            <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">{diagnosis.prognosis.timeframe}</p>
            <p className="text-xs leading-relaxed text-[var(--color-ink-soft)]">{diagnosis.prognosis.detail}</p>
          </div>
        </div>
      )}
    </div>
  );
}
