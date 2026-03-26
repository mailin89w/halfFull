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
  const [retentionChecked, setRetentionChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (hasActivePrivacyConsent()) {
      router.replace('/chapters');
    }
  }, [router]);

  const canContinue = consentChecked && retentionChecked && !submitting;

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

          <section className="rounded-[2rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
              Consent required
            </p>
            <h1 className="text-[1.9rem] font-bold leading-[1.02] tracking-[-0.05em] text-[var(--color-ink)]">
              Before we handle any health data
            </h1>
            <p className="mt-3 text-sm leading-6 text-[var(--color-ink-soft)]">
              HalfFull creates an anonymous ID, uses your answers to score fatigue-related patterns,
              and keeps stored health data only for a limited time so you can finish the assessment.
            </p>
          </section>

          <section className="section-card flex flex-col gap-4 px-5 py-5">
            <div className="rounded-[1.5rem] bg-white/70 px-4 py-4">
              <p className="text-sm font-semibold text-[var(--color-ink)]">What you’re agreeing to</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--color-ink-soft)]">
                <li>We assign a random anonymous ID instead of storing your name, email, or direct identifiers.</li>
                <li>Your answers and generated report can be stored temporarily for up to 24 hours.</li>
                <li>You can exit at any time and clear locally stored session data immediately.</li>
              </ul>
            </div>

            <label className="flex items-start gap-3 rounded-[1.25rem] border border-[rgba(9,9,15,0.08)] bg-white px-4 py-4">
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(event) => setConsentChecked(event.target.checked)}
                className="mt-1 h-4 w-4 accent-[var(--color-accent)]"
              />
              <span className="text-sm leading-6 text-[var(--color-ink)]">
                I explicitly consent to HalfFull processing my health-related answers to generate an assessment and doctor-ready report.
              </span>
            </label>

            <label className="flex items-start gap-3 rounded-[1.25rem] border border-[rgba(9,9,15,0.08)] bg-white px-4 py-4">
              <input
                type="checkbox"
                checked={retentionChecked}
                onChange={(event) => setRetentionChecked(event.target.checked)}
                className="mt-1 h-4 w-4 accent-[var(--color-accent)]"
              />
              <span className="text-sm leading-6 text-[var(--color-ink)]">
                I understand the data is tied to an anonymous ID, expires automatically, and can be cleared on explicit exit.
              </span>
            </label>

            {error && (
              <p className="text-sm text-[#b34343]">{error}</p>
            )}

            <button
              type="button"
              onClick={handleContinue}
              disabled={!canContinue}
              className="w-full rounded-full bg-[#09090f] px-5 py-4 text-base font-bold text-white disabled:cursor-not-allowed disabled:opacity-45"
            >
              {submitting ? 'Saving consent...' : 'Agree and continue'}
            </button>
          </section>
        </div>
      </main>
    </div>
  );
}
