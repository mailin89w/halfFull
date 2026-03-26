'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useAssessment } from '@/src/hooks/useAssessment';
import {
  createPrivacyConsentRecord,
  readPrivacyConsent,
  storePrivacyConsent,
} from '@/src/lib/privacy';
import {
  readStoredConfirmedConditions,
  readStoredDeepResult,
  readStoredMLScores,
} from '@/src/lib/medgemma';

export default function CreateAccountPage() {
  const router = useRouter();
  const { answers } = useAssessment();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setSubmitting(true);
    setError(null);

    const privacy = readPrivacyConsent() ?? createPrivacyConsentRecord();
    storePrivacyConsent(privacy);

    try {
      const response = await fetch('/api/account/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login,
          password,
          privacy,
          snapshot: {
            answers,
            mlScores: readStoredMLScores() ?? {},
            confirmedConditions: readStoredConfirmedConditions() ?? [],
            deepResult: readStoredDeepResult(),
          },
        }),
      });

      const data = await response.json().catch(() => ({ error: 'Could not create account.' }));
      if (!response.ok) {
        throw new Error((data as { error?: string }).error ?? 'Could not create account.');
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create account.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="phone-frame flex flex-col">
      <main className="flex-1 px-5 py-6">
        <div className="mx-auto flex max-w-lg flex-col gap-5">
          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <Link href="/results" className="text-[var(--color-ink-soft)]">Back</Link>
          </div>

          <section className="section-card px-5 py-6">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
              Save your data
            </p>
            <h1 className="text-[2rem] font-bold leading-[1.02] tracking-[-0.05em] text-[var(--color-ink)]">
              Create an account
            </h1>
            <p className="mt-3 text-sm leading-6 text-[var(--color-ink-soft)]">
              Create a login and password so we can keep your responses in Supabase and let you come back after future doctor visits or lab uploads.
            </p>

            {success ? (
              <div className="mt-5 rounded-[1.4rem] bg-[rgba(215,240,104,0.35)] px-4 py-4">
                <p className="text-sm font-semibold text-[var(--color-ink)]">
                  Account created. Your current results have been linked to it.
                </p>
                <button
                  type="button"
                  onClick={() => router.push('/results')}
                  className="mt-4 rounded-full bg-[#09090f] px-5 py-3 text-sm font-bold text-white"
                >
                  Return to results
                </button>
              </div>
            ) : (
              <div className="mt-5 flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-[var(--color-ink)]" htmlFor="login">
                    Login
                  </label>
                  <input
                    id="login"
                    value={login}
                    onChange={(e) => setLogin(e.target.value)}
                    className="w-full rounded-[1.35rem] border border-[rgba(151,166,210,0.28)] bg-white px-4 py-3 text-base text-[var(--color-ink)] focus:border-[var(--color-accent)] focus:outline-none"
                    placeholder="Choose a login"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-[var(--color-ink)]" htmlFor="password">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-[1.35rem] border border-[rgba(151,166,210,0.28)] bg-white px-4 py-3 text-base text-[var(--color-ink)] focus:border-[var(--color-accent)] focus:outline-none"
                    placeholder="At least 8 characters"
                  />
                </div>

                {error && <p className="text-sm text-[#b34343]">{error}</p>}

                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={submitting || login.trim().length < 3 || password.length < 8}
                  className="rounded-full bg-[#09090f] px-5 py-4 text-base font-bold text-white disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {submitting ? 'Creating account...' : 'Create account'}
                </button>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
