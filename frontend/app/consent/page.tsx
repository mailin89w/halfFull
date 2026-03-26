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
            <span>HalfFull</span>
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

              <div className="mt-5 rounded-[1.6rem] border border-[rgba(140,170,101,0.24)] bg-white/78 px-4 py-4 backdrop-blur-sm">
                <p className="text-sm font-semibold text-[var(--color-ink)]">Key points</p>
                <ul className="mt-3 space-y-2.5 text-sm leading-6 text-[var(--color-ink-soft)]">
                  <li>Your data is linked to a random anonymous ID, not your name.</li>
                  <li>It&apos;s stored only temporarily, for up to 24 hours.</li>
                  <li>You can leave anytime and clear this session data.</li>
                </ul>
              </div>
            </div>
          </section>

          <section className="section-card flex flex-col gap-4 px-5 py-5">
            <label className="flex items-start gap-3 rounded-[1.4rem] border border-[rgba(140,170,101,0.24)] bg-[rgba(255,255,255,0.88)] px-4 py-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(event) => setConsentChecked(event.target.checked)}
                className="mt-1 h-4 w-4 accent-[#77b255]"
              />
              <span className="text-sm leading-6 text-[var(--color-ink)]">
                I agree to HalfFull processing my health-related answers to generate my assessment and report.
              </span>
            </label>

            {error && (
              <p className="rounded-[1rem] border border-[rgba(179,67,67,0.14)] bg-[rgba(179,67,67,0.05)] px-3 py-2 text-sm text-[#b34343]">
                {error}
              </p>
            )}

            <button
              type="button"
              onClick={handleContinue}
              disabled={!canContinue}
              className="w-full rounded-full bg-[#09090f] px-5 py-4 text-base font-bold text-white transition-transform duration-150 hover:translate-y-[-1px] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {submitting ? 'Saving consent...' : 'Continue'}
            </button>

            <Link
              href="/start"
              className="text-center text-sm font-semibold text-[var(--color-ink-soft)] underline decoration-[rgba(95,103,131,0.35)] underline-offset-4 transition-colors hover:text-[var(--color-ink)]"
            >
              Back
            </Link>
          </section>
        </div>
      </main>
    </div>
  );
}
