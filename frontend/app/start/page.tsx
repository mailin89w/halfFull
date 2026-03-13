'use client';

import { useState } from 'react';
import Link from 'next/link';

const journeySteps = [
  { lead: 'Understand', rest: 'your symptom drivers' },
  { lead: 'Prepare', rest: "for your doctor's visit" },
  { lead: 'Improve', rest: 'your vitality' },
];

function CareMascot() {
  return (
    <svg viewBox="0 0 160 150" fill="none" aria-hidden="true" className="h-full w-full">
      <path
        d="M82 25c9 0 16 6 19 15 9-4 19-2 26 6 7 8 8 19 2 28 10 5 16 15 15 27-2 18-17 29-36 28-6 14-15 22-27 22-11 0-21-8-27-22-18 1-34-10-35-28-1-12 5-22 15-27-6-9-5-20 2-28 7-8 17-10 26-6 3-9 10-15 20-15Z"
        fill="#b7a4d3"
      />
      <path
        d="M86 16c0-8 8-14 16-10 7 3 11 12 8 19-3 8-11 13-19 13-3-6-5-13-5-22Z"
        fill="#d7f068"
      />
      <ellipse cx="59" cy="79" rx="13" ry="9" fill="#fff" />
      <ellipse cx="101" cy="79" rx="13" ry="9" fill="#fff" />
      <ellipse cx="63" cy="79" rx="6" ry="7" fill="#2b2d74" />
      <ellipse cx="105" cy="79" rx="6" ry="7" fill="#2b2d74" />
      <circle cx="38" cy="94" r="8" fill="#ea5aa6" opacity="0.95" />
      <circle cx="122" cy="94" r="8" fill="#ea5aa6" opacity="0.95" />
    </svg>
  );
}

function JourneyRibbon() {
  return (
    <svg
      viewBox="0 0 360 92"
      className="h-20 w-full"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="journeyGradient" x1="14" y1="46" x2="346" y2="46" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7765f4" />
          <stop offset="0.32" stopColor="#d49ac8" />
          <stop offset="0.62" stopColor="#f0af93" />
          <stop offset="1" stopColor="#d7f068" />
        </linearGradient>
      </defs>
      <g opacity="0.95">
        <circle cx="48" cy="46" r="34" fill="#7765f4" />
        <circle cx="102" cy="46" r="34" fill="#d49ac8" fillOpacity="0.82" />
        <path
          d="M135 12c22 0 32 13 45 13s23-13 45-13c28 0 49 25 49 34s-21 34-49 34c-22 0-32-13-45-13s-23 13-45 13c-28 0-49-25-49-34s21-34 49-34Z"
          fill="url(#journeyGradient)"
        />
        <circle cx="286" cy="46" r="34" fill="#edf3a8" fillOpacity="0.88" />
        <circle cx="332" cy="46" r="34" fill="#d7f068" fillOpacity="0.95" />
      </g>
    </svg>
  );
}

export default function StartPage() {
  const [faqOpen, setFaqOpen] = useState(false);

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex flex-1 flex-col px-5 py-6">
        <div className="mx-auto flex w-full max-w-lg flex-1 flex-col">
          <div className="mb-6 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <button
              type="button"
              onClick={() => setFaqOpen((value) => !value)}
              className="rounded-full border border-[rgba(9,9,15,0.12)] bg-white/75 px-3 py-1.5 text-[var(--color-ink-soft)]"
            >
              FAQ
            </button>
          </div>

          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="mb-5">
              <div className="relative">
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
                  Low-energy assessment
                </p>
                <h1 className="editorial-display text-[clamp(2.05rem,8vw,3.5rem)] leading-[0.92] text-[var(--color-ink)]">
                  YOU
                  <br />
                  REMEMBER
                  <br />
                  FEELING
                  <br />
                  GOOD.
                </h1>

                <div className="pointer-events-none absolute left-[15.3rem] top-[8.8rem] h-[6.2rem] w-[6.2rem]">
                  <CareMascot />
                </div>
              </div>
            </div>

            <p className="max-w-[18rem] text-xl font-bold leading-7 tracking-[-0.04em] text-[var(--color-ink)]">
              Let&apos;s get back there.
            </p>
            <p className="mt-3 max-w-[19rem] text-sm leading-6 text-[var(--color-ink-soft)]">
              Find the patterns behind your low energy — and walk into your next doctor&apos;s appointment actually prepared.
            </p>
          </section>

          <section className="section-card mt-5 px-5 py-6">
            <div className="mb-5 flex items-center justify-start gap-3">
              <span className="rounded-full bg-[var(--color-lime)] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--color-ink)]">
                Start here
              </span>
            </div>

            <div className="space-y-2">
              <JourneyRibbon />
              <div className="grid grid-cols-3 gap-3">
                {journeySteps.map((step) => (
                  <div key={step.lead} className="flex flex-col items-center text-center">
                    <p className="text-sm font-medium leading-5 text-[var(--color-ink)]">
                      <span className="mb-1 block text-base font-bold uppercase tracking-[-0.04em] text-[var(--color-ink)]">
                        {step.lead}
                      </span>
                      <span className="block">{step.rest}</span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <p className="mt-5 text-center text-xs leading-5 text-[var(--color-ink-soft)]">
            Based on clinical research · Used by 14,000+ people · Trusted by Doctolib
          </p>

          <div className="mt-auto pt-6">
            <Link
              href="/assessment"
              className="block w-full rounded-full px-5 py-4 text-center text-base font-bold shadow-[0_10px_24px_rgba(9,9,15,0.22)] transition-all active:scale-[0.98]"
              style={{ backgroundColor: '#09090f', color: '#ffffff' }}
            >
              Take the 10-minute assessment test
            </Link>

            {faqOpen && (
              <div className="section-card mt-4 bg-[rgba(248,248,251,0.92)] px-5 py-4">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-[var(--color-ink)]">
                    FAQ
                  </h3>
                  <button
                    type="button"
                    onClick={() => setFaqOpen(false)}
                    className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]"
                  >
                    Close
                  </button>
                </div>
                <div className="space-y-3 text-sm leading-5 text-[var(--color-ink-soft)]">
                  <div>
                    <p className="font-bold text-[var(--color-ink)]">What is HalfFull?</p>
                    <p>It turns your symptom answers into a clearer fatigue report for your next doctor visit.</p>
                  </div>
                  <div>
                    <p className="font-bold text-[var(--color-ink)]">Why MedGemma?</p>
                    <p>MedGemma adds short medical summaries and next-step suggestions that are easier to act on.</p>
                  </div>
                  <div>
                    <p className="font-bold text-[var(--color-ink)]">Why NHANES?</p>
                    <p>NHANES gives the scoring a real population-health baseline, which makes results less generic.</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
