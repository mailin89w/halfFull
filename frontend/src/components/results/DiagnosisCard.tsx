'use client';

import { useState } from 'react';
import type { BayesianConditionTrace } from '@/src/lib/medgemma';
import type { Diagnosis } from '@/src/lib/mockResults';
import type { ConfidenceTier, UrgencyLevel } from '@/src/lib/clinicalSignals';

interface Props {
  diagnosis: Diagnosis;
  personalNote?: string;
  confidence?: {
    tier: ConfidenceTier;
    summary: string;
  };
  urgency?: {
    level: UrgencyLevel;
    summary: string;
  };
  reasoningTrace?: {
    mlScore?: number;
    threshold?: number;
    bayesian?: BayesianConditionTrace | null;
    synthesisSummary?: string;
  };
}

const CONFIDENCE_CONFIG: Record<ConfidenceTier, { label: string; bg: string; text: string }> = {
  high: {
    label: 'High confidence',
    bg: 'bg-[#d7f06859]',
    text: 'text-[var(--color-ink)]',
  },
  medium: {
    label: 'Medium confidence',
    bg: 'bg-[#d7f06859]',
    text: 'text-[var(--color-ink)]',
  },
  low: {
    label: 'Low confidence',
    bg: 'bg-[#d7f06859]',
    text: 'text-[var(--color-ink)]',
  },
};

const URGENCY_CONFIG: Record<UrgencyLevel, { label: string; bg: string; text: string; border: string }> = {
  urgent: {
    label: 'Urgent',
    bg: 'bg-[#efb9732e]',
    text: 'text-[var(--color-ink)]',
    border: 'border-[#efb9732e]',
  },
  soon: {
    label: 'Soon',
    bg: 'bg-[#efb9732e]',
    text: 'text-[var(--color-ink)]',
    border: 'border-[#efb9732e]',
  },
  routine: {
    label: 'Routine',
    bg: 'bg-[#efb9732e]',
    text: 'text-[var(--color-ink)]',
    border: 'border-[#efb9732e]',
  },
};

function ReasoningTrace({
  trace,
}: {
  trace: NonNullable<Props['reasoningTrace']>;
}) {
  const [open, setOpen] = useState(false);
  const applied = trace.bayesian?.lrs_applied ?? [];
  const bayesSummary = trace.bayesian
    ? `Bayesian: ${trace.bayesian.prior.toFixed(2)} -> ${trace.bayesian.posterior.toFixed(2)}`
    : 'Bayesian: no clarification update';

  return (
    <div className="rounded-2xl border border-[rgba(151,166,210,0.18)] bg-white">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
          How we reached this
        </p>
        <span className="text-sm font-semibold text-[var(--color-ink-soft)]">
          {open ? 'Hide' : 'Show'}
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-[rgba(151,166,210,0.18)] p-4 pt-3">
          <div className="rounded-[1rem] bg-[rgba(119,101,244,0.06)] px-3 py-3">
            <p className="text-xs font-semibold text-[var(--color-ink)]">1. ML score</p>
            <p className="mt-1 text-sm leading-6 text-[var(--color-ink-soft)]">
              {trace.mlScore !== undefined
                ? `ML: scored ${trace.mlScore.toFixed(2)} (threshold ${trace.threshold?.toFixed(2) ?? '0.40'})`
                : 'ML score unavailable'}
            </p>
          </div>

          <div className="rounded-[1rem] bg-[rgba(215,240,104,0.14)] px-3 py-3">
            <p className="text-xs font-semibold text-[var(--color-ink)]">2. Bayesian update</p>
            <p className="mt-1 text-sm leading-6 text-[var(--color-ink-soft)]">{bayesSummary}</p>
            {applied.length > 0 && (
              <div className="mt-2 space-y-1">
                {applied.slice(0, 3).map((entry, index) => (
                  <p key={`${entry.question_id}-${index}`} className="text-xs leading-5 text-[var(--color-ink-soft)]">
                    {entry.questionText ?? entry.question_id}: {entry.answerLabel ?? entry.answer} {'->'} LR {entry.lr.toFixed(2)}
                  </p>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-[1rem] bg-[rgba(158,169,211,0.14)] px-3 py-3">
            <p className="text-xs font-semibold text-[var(--color-ink)]">3. MedGemma synthesis</p>
            <p className="mt-1 text-sm leading-6 text-[var(--color-ink-soft)]">
              {trace.synthesisSummary ?? 'Synthesis: included in MedGemma report narrative'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export function DiagnosisCard({ diagnosis, personalNote, confidence, urgency, reasoningTrace }: Props) {
  const [open, setOpen] = useState(false);
  const confidenceCfg = confidence ? CONFIDENCE_CONFIG[confidence.tier] : null;
  const urgencyCfg = urgency ? URGENCY_CONFIG[urgency.level] : null;

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
        <span className="text-[2rem] leading-none flex-shrink-0">{diagnosis.emoji}</span>

        <div className="min-w-0 flex-1">
          <p className="card-title text-[1.15rem] font-black leading-snug tracking-[-0.03em] text-[var(--color-ink)]">
            {diagnosis.title}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {confidenceCfg && (
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${confidenceCfg.bg} ${confidenceCfg.text}`}>
                {confidenceCfg.label}
              </span>
            )}
            {urgencyCfg && (
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${urgencyCfg.bg} ${urgencyCfg.text} ${urgencyCfg.border}`}>
                {urgencyCfg.label}
              </span>
            )}
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
        <div className="flex flex-col gap-10 border-t border-[rgba(151,166,210,0.18)] bg-[var(--color-card)] px-5 pb-6 pt-4">
          {personalNote && (
            <div className="flex gap-2.5 rounded-2xl border border-[rgba(119,101,244,0.12)] bg-[var(--color-accent-soft)] px-4 py-3">
              <span className="text-base flex-shrink-0">✨</span>
              <p className="text-xs leading-relaxed text-[var(--color-ink)]">{personalNote}</p>
            </div>
          )}

          <p className="text-sm leading-6 text-[var(--color-ink-soft)]">{diagnosis.description}</p>

          {(confidence || urgency) && (
            <div className="grid gap-4 sm:grid-cols-2">
              {confidence && (
                <div className="min-w-0 rounded-2xl border border-[#d7f06859] bg-[#d7f06859] p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                    Confidence
                  </p>
                  <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                    {CONFIDENCE_CONFIG[confidence.tier].label}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-ink-soft)]">
                    {confidence.summary}
                  </p>
                </div>
              )}
              {urgency && (
                <div className={`min-w-0 rounded-2xl border p-4 ${URGENCY_CONFIG[urgency.level].border} ${URGENCY_CONFIG[urgency.level].bg}`}>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                    Urgency
                  </p>
                  <p className={`mt-1 text-sm font-semibold ${URGENCY_CONFIG[urgency.level].text}`}>
                    {URGENCY_CONFIG[urgency.level].label}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-ink-soft)]">
                    {urgency.summary}
                  </p>
                </div>
              )}
            </div>
          )}

          {reasoningTrace && <ReasoningTrace trace={reasoningTrace} />}

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
