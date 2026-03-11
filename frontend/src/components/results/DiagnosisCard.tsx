'use client';

import { useState } from 'react';
import type { Diagnosis, SignalStrength } from '@/src/lib/mockResults';

interface Props {
  diagnosis: Diagnosis;
  rank: number;
}

const SIGNAL_CONFIG: Record<
  SignalStrength,
  { label: string; dotColor: string; pillBg: string; pillText: string }
> = {
  strong: {
    label: 'Strong signal',
    dotColor: 'bg-[#EFB973]',
    pillBg: 'bg-[#EFB973]/20',
    pillText: 'text-[#254662]',
  },
  moderate: {
    label: 'Moderate signal',
    dotColor: 'bg-[#EFD17B]',
    pillBg: 'bg-[#EFD17B]/25',
    pillText: 'text-[#254662]',
  },
  investigating: {
    label: 'Worth investigating',
    dotColor: 'bg-[#A2B6CB]',
    pillBg: 'bg-[#A2B6CB]/20',
    pillText: 'text-[#254662]',
  },
};

export function DiagnosisCard({ diagnosis, rank }: Props) {
  const [open, setOpen] = useState(false);
  const cfg = SIGNAL_CONFIG[diagnosis.signal];

  return (
    <div
      className={[
        'rounded-2xl border-2 overflow-hidden transition-all duration-200',
        open ? 'border-[#EFB973]/60' : 'border-[#A2B6CB]/25',
      ].join(' ')}
    >
      {/* Header row — always visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-5 py-4 flex items-center gap-4 bg-white hover:bg-[#FAF7F2] transition-colors text-left"
      >
        {/* Rank bubble */}
        <span className="w-7 h-7 rounded-full bg-[#254662] text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
          {rank}
        </span>

        {/* Emoji */}
        <span className="text-2xl flex-shrink-0">{diagnosis.emoji}</span>

        {/* Title + signal */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[#254662] text-sm leading-snug">{diagnosis.title}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dotColor}`} />
            <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${cfg.pillBg} ${cfg.pillText}`}>
              {cfg.label}
            </span>
          </div>
        </div>

        {/* Chevron */}
        <svg
          width="18"
          height="18"
          viewBox="0 0 18 18"
          fill="none"
          className={`flex-shrink-0 text-[#A2B6CB] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M4.5 6.75L9 11.25L13.5 6.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Expanded body */}
      {open && (
        <div className="px-5 pb-5 pt-1 bg-white flex flex-col gap-5 border-t border-[#A2B6CB]/15">
          {/* Description */}
          <p className="text-sm text-[#A2B6CB] leading-relaxed">{diagnosis.description}</p>

          {/* Lab tests */}
          <div>
            <h4 className="text-xs font-semibold text-[#254662] uppercase tracking-wide mb-3">
              Tests to request from your GP
            </h4>
            <div className="flex flex-col gap-2.5">
              {diagnosis.tests.map((test) => (
                <div key={test.name} className="flex items-start gap-2.5">
                  <span className="mt-0.5 text-[#EFB973] font-bold text-xs flex-shrink-0">•</span>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-[#254662]">{test.name}</span>
                      {test.mustRequest && (
                        <span className="text-[10px] font-semibold bg-[#EFB973]/25 text-[#254662] px-2 py-0.5 rounded-full whitespace-nowrap">
                          ⚠ request explicitly
                        </span>
                      )}
                    </div>
                    {test.note && (
                      <p className="text-xs text-[#A2B6CB] mt-0.5 leading-snug">{test.note}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Prognosis */}
          <div className="rounded-xl bg-[#C7D9A7]/20 border border-[#C7D9A7]/40 p-4 flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-base">🌱</span>
              <span className="text-xs font-semibold text-[#254662] uppercase tracking-wide">Recovery outlook</span>
            </div>
            <p className="text-sm font-semibold text-[#254662] mt-1">{diagnosis.prognosis.timeframe}</p>
            <p className="text-xs text-[#A2B6CB] leading-relaxed">{diagnosis.prognosis.detail}</p>
          </div>
        </div>
      )}
    </div>
  );
}
