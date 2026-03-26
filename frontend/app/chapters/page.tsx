'use client';

import Link from 'next/link';
import { clearStoredMedGemmaResult } from '@/src/lib/medgemma';

const CHAPTERS = [
  {
    id: 'profile',
    title: 'About You',
    description: 'Age, sex, height and weight — the baseline for everything that follows.',
    color: '#9ea9d3',
    emoji: '🧬',
  },
  {
    id: 'sleep',
    title: 'Sleep',
    description: 'Hours, quality, snoring patterns and trouble falling or staying asleep.',
    color: '#a89de8',
    emoji: '🌙',
  },
  {
    id: 'activity',
    title: 'Activity & Work',
    description: 'Exercise habits, work schedule, and how much time you spend sitting each day.',
    color: '#7765f4',
    emoji: '⚡',
  },
  {
    id: 'lifestyle',
    title: 'Lifestyle',
    description: 'Diet quality, alcohol intake, and smoking — habits that shape your energy.',
    color: '#d49ac8',
    emoji: '🥑',
  },
  {
    id: 'health_history',
    title: 'Medical History',
    description: 'Blood pressure, current medications and a few key past diagnoses.',
    color: '#f0af93',
    emoji: '📋',
  },
  {
    id: 'conditions',
    title: 'Health Conditions',
    description: "Diagnoses a doctor has already confirmed — so we don't re-flag what you know.",
    color: '#e8b86d',
    emoji: '✅',
  },
  {
    id: 'symptoms',
    title: 'Your Symptoms',
    description: "Physical and emotional patterns you've been noticing — tiredness, pain, mood.",
    color: '#7ec8a4',
    emoji: '💬',
  },
  {
    id: 'womens_health',
    title: "Women's Health",
    description: 'Hormonal and reproductive factors, if applicable to you.',
    color: '#b8d96b',
    emoji: '🌸',
  },
  {
    id: 'labs',
    title: 'Recent Labs',
    description: 'Upload or enter blood test values you already have — entirely optional.',
    color: '#7765f4',
    emoji: '🔬',
  },
];

export default function ChaptersPage() {
  return (
    <div className="phone-frame flex flex-col">
      <main className="flex-1 overflow-y-auto px-5 py-6">
        <div className="mx-auto flex max-w-lg flex-col gap-4">

          {/* Header */}
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <Link href="/start" className="text-[var(--color-ink-soft)]">Back</Link>
          </div>

          {/* Hero card */}
          <section className="rounded-[2rem] bg-[var(--color-card)] px-5 py-5 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
              10-minute assessment
            </p>
            <h1 className="text-[1.75rem] font-bold leading-[1.05] tracking-[-0.05em] text-[var(--color-ink)]">
              Here&apos;s what<br />we&apos;ll cover
            </h1>
            <p className="mt-2 text-sm leading-[1.6] text-[var(--color-ink-soft)]">
              {CHAPTERS.length} short chapters, one area at a time. No wrong answers.
            </p>

            {/* Coloured segment preview */}
            <div className="mt-4 flex gap-[3px]">
              {CHAPTERS.map((ch) => (
                <div
                  key={ch.id}
                  className="h-[5px] flex-1 rounded-full"
                  style={{ backgroundColor: ch.color }}
                />
              ))}
            </div>
          </section>

          {/* Chapter list */}
          <div className="flex flex-col divide-y divide-[rgba(151,166,210,0.18)] rounded-[1.75rem] bg-[var(--color-card)] shadow-[0_8px_24px_rgba(86,98,145,0.10)]">
            {CHAPTERS.map((ch, i) => (
              <div
                key={ch.id}
                className={[
                  'flex items-center gap-3 px-4 py-3',
                  i === 0 && 'pt-4',
                  i === CHAPTERS.length - 1 && 'pb-4',
                ].filter(Boolean).join(' ')}
              >
                {/* Coloured left accent + emoji */}
                <div
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-base"
                  style={{ backgroundColor: ch.color + '28' }}
                >
                  {ch.emoji}
                </div>

                {/* Text */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="text-[9px] font-bold tabular-nums"
                      style={{ color: ch.color }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span className="text-sm font-bold text-[var(--color-ink)]">{ch.title}</span>
                  </div>
                  <p className="text-[0.78rem] leading-[1.45] text-[var(--color-ink-soft)]">
                    {ch.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* CTA */}
          <Link
            href="/assessment"
            onClick={() => clearStoredMedGemmaResult()}
            className="block w-full rounded-full px-5 py-4 text-center text-base font-bold shadow-[0_10px_24px_rgba(9,9,15,0.22)] transition-all active:scale-[0.98]"
            style={{ backgroundColor: '#09090f', color: '#ffffff' }}
          >
            Let&apos;s start
          </Link>

          <p className="text-center text-[11px] leading-4 text-[var(--color-ink-soft)]">
            For educational use only. Not a substitute for medical advice.
          </p>

        </div>
      </main>
    </div>
  );
}
