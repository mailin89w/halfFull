'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  clearStoredHealthData,
  createPrivacyConsentRecord,
  hasActivePrivacyConsent,
  storePrivacyConsent,
} from '@/src/lib/privacy';

export default function ConsentPage() {
  const router = useRouter();
  const [consentChecked, setConsentChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const checkboxId = 'privacy-consent';

  useEffect(() => {
    if (hasActivePrivacyConsent()) {
      router.replace('/chapters');
    }
  }, [router]);

  const canContinue = consentChecked && !submitting;

  const handleContinue = async () => {
    if (!canContinue) return;

    setSubmitting(true);
    setError(null);

    const privacy = createPrivacyConsentRecord();
    storePrivacyConsent(privacy);

    try {
      const response = await fetch('/api/privacy/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          privacy,
          source: 'consent_page',
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({ error: 'Could not save consent.' }));
        throw new Error((data as { error?: string }).error ?? 'Could not save consent.');
      }

      router.push('/chapters');
    } catch (err) {
      clearStoredHealthData();
      setSubmitting(false);
      setError(err instanceof Error ? err.message : 'Could not save consent.');
    }
  };

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex-1 px-5 py-6">
        <div className="mx-auto flex max-w-lg flex-col gap-4">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span style={{ fontFamily: 'Archivo, sans-serif', letterSpacing: '-0.02em', textTransform: 'none', fontSize: 16, lineHeight: 1 }}><span style={{ fontWeight: 400, color: 'var(--color-ink-soft)' }}>half</span><span style={{ fontWeight: 900, color: 'var(--color-ink)' }}>Full</span></span>
            <Link href="/start" className="text-[var(--color-ink-soft)]">Back</Link>
          </div>

          <section className="relative overflow-hidden rounded-[2rem] border border-[rgba(151,166,210,0.28)] bg-[linear-gradient(180deg,rgba(248,248,251,0.98),rgba(238,245,224,0.95))] px-5 py-6 shadow-[0_18px_40px_rgba(86,98,145,0.14)]">
            <div className="absolute -right-8 top-4 h-28 w-28 rounded-full bg-[rgba(215,240,104,0.32)] blur-2xl" />
            <div className="absolute left-6 top-0 h-20 w-20 rounded-full bg-[rgba(179,224,110,0.18)] blur-2xl" />

            <div className="relative">
              <span className="inline-flex rounded-full bg-[var(--color-lime)] px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
                Privacy notice
              </span>
              <h1 className="mt-4 text-[1.95rem] font-bold leading-[1.02] tracking-[-0.05em] text-[var(--color-ink)]">
                Before we process your health answers
              </h1>
              <p className="mt-4 max-w-[30ch] text-sm leading-6 text-[var(--color-ink-soft)]">
                We use your answers to generate your fatigue assessment and doctor-ready report.
              </p>
            </div>
          </section>

          <section className="section-card flex flex-col gap-4 px-5 py-5">
            <p className="text-sm font-semibold text-[var(--color-ink)]">We care about your privacy</p>

            <ul className="space-y-2.5 text-sm leading-6 text-[var(--color-ink-soft)]">
              <li className="flex items-start gap-2.5">
                <span
                  aria-hidden="true"
                  className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(215,240,104,0.45)] text-[var(--color-ink)]"
                >
                  <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m3.5 8 3 3 6-6" />
                  </svg>
                </span>
                <span>Your data is linked to a random anonymous ID, not your name.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span
                  aria-hidden="true"
                  className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(215,240,104,0.45)] text-[var(--color-ink)]"
                >
                  <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m3.5 8 3 3 6-6" />
                  </svg>
                </span>
                <span>It&apos;s stored only temporarily, for up to 24 hours.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span
                  aria-hidden="true"
                  className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(215,240,104,0.45)] text-[var(--color-ink)]"
                >
                  <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m3.5 8 3 3 6-6" />
                  </svg>
                </span>
                <span>You can leave anytime and clear this session data.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span
                  aria-hidden="true"
                  className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(215,240,104,0.45)] text-[var(--color-ink)]"
                >
                  <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m3.5 8 3 3 6-6" />
                  </svg>
                </span>
                <span>
                  Your data is processed and stored in line with our{' '}
                  <span className="font-bold text-[var(--color-accent)]">Privacy Policy</span>.
                </span>
              </li>
            </ul>

            <div className="mt-1 rounded-[1.4rem] bg-[rgba(248,248,251,0.7)] p-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                Your agreement
              </p>
              <label
                htmlFor={checkboxId}
                className="mt-3 flex cursor-pointer items-start gap-3 rounded-[1rem] border border-[rgba(151,166,210,0.22)] bg-white/65 px-3 py-3 transition-colors hover:bg-white/78"
              >
                <input
                  id={checkboxId}
                  type="checkbox"
                  checked={consentChecked}
                  onChange={(event) => setConsentChecked(event.target.checked)}
                  className="mt-1 h-4 w-4 shrink-0"
                  style={{ accentColor: 'var(--color-lime)' }}
                />
                <span className="text-sm leading-6 text-[var(--color-ink)]">
                  I agree to HalfFull processing my health-related answers to generate my assessment and report.
                </span>
              </label>
            </div>
          </section>

          <div className="flex flex-col gap-4 px-1">
            {error && (
              <p className="rounded-[1rem] border border-[rgba(179,67,67,0.14)] bg-[rgba(255,248,248,0.7)] px-3 py-2 text-sm text-[#b34343]">
                {error}
              </p>
            )}

            <button
              type="button"
              onClick={handleContinue}
              disabled={!canContinue}
              className="w-full rounded-full bg-[#09090f] px-5 py-4 text-base font-bold text-white transition-transform duration-150 hover:translate-y-[-1px] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {submitting ? 'Saving consent...' : 'Agree and continue'}
            </button>

            {!consentChecked && !submitting && (
              <p className="text-center text-sm text-[var(--color-ink-soft)]">
                Please confirm consent to continue.
              </p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
