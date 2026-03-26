'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

const outcomeCards = [
  'List of most probable causes',
  'Clear next steps to look into',
  'Doctor-ready summary of your situation',
];

const journeySteps = [
  {
    lead: 'Take the quiz',
    rest: 'Answer a short set of questions about your symptoms and daily habits.',
  },
  {
    lead: 'Pattern analysis',
    rest: 'Your answers are compared to medical survey data to identify relevant fatigue patterns.',
  },
  {
    lead: 'Get your results',
    rest: 'See up to 3 possible causes for your fatigue and what to discuss with your doctor.',
  },
];

const comparisonRows = [
  {
    halfFull: 'Structured symptom input',
    genericAi: 'One vague prompt',
  },
  {
    halfFull: 'Built for fatigue specifically',
    genericAi: 'General health advice',
  },
  {
    halfFull: 'Clear priorities',
    genericAi: 'Long, unfocused answers',
  },
  {
    halfFull: 'Helps you prepare for a doctor',
    genericAi: 'Not actionable',
  },
];

const faqs = [
  {
    question: 'What does HalfFull actually do?',
    answer:
      'HalfFull guides you through a short questionnaire and turns your answers into possible causes, clear priorities, and a summary you can bring to your doctor.',
  },
  {
    question: 'Does it give me a diagnosis?',
    answer:
      'No. It does not diagnose conditions. It helps you organize what may be worth discussing with a clinician.',
  },
  {
    question: 'How long does it take?',
    answer:
      'Most people finish in about 10 minutes.',
  },
  {
    question: 'Is it still useful if I do not have lab values?',
    answer:
      'Yes. It can still be useful based on symptoms and history alone. Lab results can add context later, but they are not required.',
  },
  {
    question: 'Does this replace seeing a doctor?',
    answer:
      'No. It is meant to support a doctor visit, not replace one.',
  },
  {
    question: 'Is my data safe?',
    answer:
      'Your answers stay within the product experience needed to generate your results. Review the product privacy details for the latest information about storage and handling.',
  },
  {
    question: 'Is this medical advice?',
    answer:
      'No. HalfFull is an informational support tool. It does not provide medical advice, diagnosis, or treatment.',
  },
  {
    question: 'Can HalfFull be wrong?',
    answer:
      'Yes. The results are not a diagnosis and may miss context or point to the wrong explanation. Use them as structured support for a conversation with your doctor.',
  },
];

function BrandLockup() {
  return (
    <p className="editorial-display bg-[linear-gradient(135deg,#5550a3_0%,#7468ed_44%,#9b83c4_78%,#b196ae_100%)] bg-clip-text text-[2rem] leading-none text-transparent">
      HalfFull
    </p>
  );
}

function StepPill({ index }: { index: number }) {
  const pillClasses = [
    'border-[rgba(119,101,244,0.18)] bg-[rgba(119,101,244,0.1)] text-[#5b52ba]',
    'border-[rgba(212,154,200,0.2)] bg-[rgba(212,154,200,0.12)] text-[#9d5f86]',
    'border-[rgba(215,240,104,0.24)] bg-[rgba(215,240,104,0.16)] text-[#6b7d1d]',
  ];

  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.12em] ${pillClasses[index]}`}
    >
      Step {index + 1}
    </span>
  );
}

function HeaderCheckIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-3.5 w-3.5" fill="none">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="m4.5 8.1 2.2 2.2 4.8-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HeaderCrossIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-3.5 w-3.5" fill="none">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.5 5.5 10.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M10.5 5.5 5.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function FaqChevron({ isOpen }: { isOpen: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      aria-hidden="true"
      className={`h-4 w-4 transition-transform duration-200 ${isOpen ? 'rotate-90' : 'rotate-0'}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m7 4 6 6-6 6" />
    </svg>
  );
}

function FaqItem({
  answer,
  index,
  isOpen,
  onToggle,
  question,
}: {
  answer: string;
  index: number;
  isOpen: boolean;
  onToggle: () => void;
  question: string;
}) {
  const panelId = `faq-panel-${index}`;
  const buttonId = `faq-button-${index}`;

  return (
    <div
      className={`rounded-[1.4rem] border px-4 py-2 transition-colors ${
        isOpen
          ? 'border-[rgba(119,101,244,0.2)] bg-white/84 shadow-[0_14px_26px_rgba(86,98,145,0.08)]'
          : 'border-[rgba(151,166,210,0.22)] bg-white/62'
      }`}
    >
      <button
        id={buttonId}
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-4 py-4 text-left"
      >
        <span className="pr-2 text-[1rem] font-bold leading-6 text-[var(--color-ink)]">{question}</span>
        <span
          aria-hidden="true"
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-colors ${
            isOpen
              ? 'border-[rgba(119,101,244,0.24)] bg-[rgba(119,101,244,0.1)] text-[var(--color-accent)]'
              : 'border-[rgba(151,166,210,0.22)] bg-[var(--color-card-muted)] text-[var(--color-ink)]'
          }`}
        >
          <FaqChevron isOpen={isOpen} />
        </span>
      </button>
      {isOpen ? (
        <div
          id={panelId}
          role="region"
          aria-labelledby={buttonId}
          className="border-t border-[rgba(151,166,210,0.18)] pb-5 pt-4 pr-6 text-base leading-7 text-[var(--color-ink-soft)]"
        >
          {answer}
        </div>
      ) : null}
    </div>
  );
}

export default function StartPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [showStickyCta, setShowStickyCta] = useState(false);
  const heroCtaRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const heroCta = heroCtaRef.current;

    if (!heroCta || typeof IntersectionObserver === 'undefined') {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setShowStickyCta(!entry.isIntersecting);
      },
      {
        threshold: 0.35,
      },
    );

    observer.observe(heroCta);

    return () => observer.disconnect();
  }, []);

  return (
    <div className="phone-frame flex flex-col">
      <main className="safe-bottom-padding flex flex-1 flex-col px-5 py-6">
        <div className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-9">
          <header className="flex items-center justify-between">
            <BrandLockup />
          </header>

          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-6 py-8 shadow-[0_16px_34px_rgba(86,98,145,0.11)]">
            <div className="absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_top,_rgba(119,101,244,0.13),_transparent_74%)]" />
            <div className="pointer-events-none absolute -left-10 top-6 h-32 w-32 rounded-full bg-[rgba(119,101,244,0.1)] blur-[54px]" />
            <div className="pointer-events-none absolute -right-5 top-20 h-36 w-36 rounded-full bg-[rgba(212,154,200,0.1)] blur-[60px]" />
            <div className="pointer-events-none absolute left-16 bottom-8 h-28 w-28 rounded-full bg-[rgba(215,240,104,0.08)] blur-[56px]" />
            <div className="relative">
              <h1 className="editorial-display text-[clamp(2.1rem,8vw,3.2rem)] leading-[1.1] tracking-[0.2rem] text-[var(--color-ink)]">
                Finally understand
                <br />
                your fatigue
              </h1>

              <p className="mt-7 max-w-[21rem] text-[1.08rem] leading-8 text-[var(--color-ink)]">
                Tired of not being taken seriously? Get clarity before your next doctor visit.
              </p>

              <div ref={heroCtaRef} className="mt-9">
                <Link
                  href="/chapters"
                  className="block w-full rounded-full px-5 py-4 text-center text-base font-bold shadow-[0_14px_28px_rgba(9,9,15,0.2)] transition-all duration-200 active:scale-[0.98]"
                  style={{ backgroundColor: '#09090f', color: '#ffffff' }}
                  aria-label="Start the fatigue quiz"
                >
                  Start the fatigue quiz
                </Link>
              </div>
            </div>
          </section>

          <section className="section-card px-6 py-8">
            <div className="mb-7">
              <h2 className="card-title text-[1.72rem] font-black tracking-[-0.05em] text-[var(--color-ink)]">
                What you get
              </h2>
            </div>

            <div className="space-y-4">
              {outcomeCards.map((item) => (
                <div key={item} className="flex items-start gap-3">
                  <span
                    aria-hidden="true"
                    className="mt-1 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[rgba(119,101,244,0.1)] text-[0.82rem] font-bold text-[var(--color-accent)]"
                  >
                    &#10003;
                  </span>
                  <p className="text-[1.04rem] font-bold leading-7 tracking-[-0.02em] text-[var(--color-ink)]">{item}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="section-card px-6 py-8">
            <div className="mb-7">
              <h2 className="card-title text-[1.72rem] font-black tracking-[-0.05em] text-[var(--color-ink)]">
                How it works
              </h2>
            </div>

            <div className="space-y-6">
              {journeySteps.map((step, index) => (
                <div key={step.lead} className="relative border-b border-[rgba(151,166,210,0.16)] pb-6 last:border-b-0 last:pb-0">
                  <div className="mb-3">
                    <StepPill index={index} />
                  </div>
                  <h3 className="text-[1.06rem] font-bold leading-6 tracking-[-0.02em] text-[var(--color-ink)]">{step.lead}</h3>
                  <p className="mt-2 text-base leading-7 text-[var(--color-ink-soft)]">{step.rest}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="section-card overflow-hidden px-0 py-0">
            <div className="px-6 py-7">
              <h2 className="card-title text-[1.72rem] font-black tracking-[-0.05em] text-[var(--color-ink)]">
                Built for fatigue &mdash; not generic advice
              </h2>
            </div>

            <div className="relative px-6 py-5 before:absolute before:bottom-5 before:left-1/2 before:top-5 before:w-px before:-translate-x-1/2 before:bg-[rgba(151,166,210,0.2)] before:content-['']">
              <div className="grid grid-cols-2 gap-0 border-b border-[rgba(151,166,210,0.2)] pb-4 text-[0.68rem] font-medium uppercase tracking-[0.1em] text-[var(--color-ink-soft)]">
                <div className="flex items-center justify-center gap-2 px-4 py-2 text-center text-[var(--color-ink)]">
                  <HeaderCheckIcon />
                  <span>HalfFull</span>
                </div>
                <div className="flex items-center justify-center gap-2 px-4 py-2 text-center">
                  <HeaderCrossIcon />
                  <span>Generic AI</span>
                </div>
              </div>

              <div className="relative">
                {comparisonRows.map((row, index) => (
                  <div
                    key={`${row.halfFull}-${index}`}
                    className="grid grid-cols-2 gap-0 py-4"
                  >
                    <div className="px-2 pr-4 text-[0.95rem] leading-6 text-[var(--color-ink)]">
                      {row.halfFull}
                    </div>
                    <div className="pl-4 text-[0.95rem] leading-6 text-[var(--color-ink-soft)]">
                      {row.genericAi}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="px-1 py-2">
            <div className="mb-6">
              <h2 className="card-title text-[1.72rem] font-black tracking-[-0.05em] text-[var(--color-ink)]">FAQ</h2>
            </div>

            <div className="space-y-4">
              {faqs.map((item, index) => (
                <FaqItem
                  key={item.question}
                  index={index}
                  question={item.question}
                  answer={item.answer}
                  isOpen={openFaq === index}
                  onToggle={() => setOpenFaq((current) => (current === index ? null : index))}
                />
              ))}
            </div>
          </section>

          <section className="border-t border-[rgba(151,166,210,0.24)] px-1 pt-7 pb-4">
            <p className="text-[0.88rem] leading-6 text-[rgba(95,103,131,0.92)]">
              HalfFull does not provide medical diagnoses or treatment. It helps you prepare for a
              conversation with a healthcare professional.
            </p>
          </section>
        </div>
      </main>

      <div
        className={`safe-bottom-offset pointer-events-none fixed inset-x-0 bottom-0 z-20 mx-auto flex w-full max-w-[27rem] justify-center px-5 transition-all duration-300 ${
          showStickyCta ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
        }`}
      >
        <Link
          href="/chapters"
          className="pointer-events-auto block min-h-14 w-full rounded-full border border-[rgba(151,166,210,0.22)] bg-[rgba(9,9,15,0.96)] px-5 py-4 text-center text-base font-bold text-white shadow-[0_22px_40px_rgba(9,9,15,0.24)] backdrop-blur-sm transition-all duration-200 active:scale-[0.98]"
          style={{ color: '#ffffff' }}
          aria-label="Start the fatigue quiz"
        >
          Start the fatigue quiz
        </Link>
      </div>
    </div>
  );
}
