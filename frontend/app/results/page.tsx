'use client';

import Link from 'next/link';
import { useAssessment } from '@/src/hooks/useAssessment';
import { computeResults } from '@/src/lib/mockResults';
import { EnergySpectrum } from '@/src/components/results/EnergySpectrum';
import { DiagnosisCard } from '@/src/components/results/DiagnosisCard';
import { DoctorPriority } from '@/src/components/results/DoctorPriority';

export default function ResultsPage() {
  const { answers, hydrated, reset } = useAssessment();

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center">
        <p className="text-[#A2B6CB] text-sm">Loading…</p>
      </div>
    );
  }

  const { currentPct, projectedPct, summaryLine, diagnoses, doctors } =
    computeResults(answers);

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col">
      {/* Header */}
      <header className="px-5 pt-6 pb-3 sticky top-0 bg-[#FAF7F2]/90 backdrop-blur-sm z-10">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <span className="text-[#254662] font-semibold text-lg tracking-tight">HalfFull</span>
          <Link
            href="/assessment"
            className="text-sm text-[#A2B6CB] hover:text-[#254662] transition-colors"
          >
            ← Back to questions
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 px-5 py-4 pb-10">
        <div className="max-w-lg mx-auto flex flex-col gap-5">

          {/* Intro line */}
          <div className="pt-1">
            <h1 className="text-2xl font-semibold text-[#254662] leading-snug">
              Here's what your answers reveal
            </h1>
            <p className="text-sm text-[#A2B6CB] mt-1">{summaryLine}</p>
          </div>

          {/* ── Section 1: Energy Spectrum ── */}
          <EnergySpectrum currentPct={currentPct} projectedPct={projectedPct} />

          {/* ── Section 2: Fatigue Drivers ── */}
          <div className="flex flex-col gap-3">
            <div>
              <h2 className="text-base font-semibold text-[#254662]">
                Areas worth investigating with your doctor
              </h2>
              <p className="text-xs text-[#A2B6CB] mt-0.5">
                Tap each to see recommended tests and recovery outlook.
              </p>
            </div>

            {diagnoses.map((d, i) => (
              <DiagnosisCard key={d.id} diagnosis={d} rank={i + 1} />
            ))}
          </div>

          {/* ── Section 3: Doctor Priority ── */}
          <DoctorPriority doctors={doctors} />

          {/* ── Footer actions ── */}
          <div className="flex flex-col gap-3 pt-2">
            <Link
              href="/assessment"
              className="w-full py-4 rounded-2xl bg-[#EFB973] text-[#254662] font-semibold text-base text-center hover:bg-[#e8ae62] transition-all active:scale-[0.98]"
            >
              ← Review my answers
            </Link>
            <button
              onClick={() => {
                reset();
                window.location.href = '/assessment';
              }}
              className="w-full py-4 rounded-2xl border-2 border-[#A2B6CB]/35 text-[#254662] font-semibold text-base hover:border-[#A2B6CB]/60 transition-all"
            >
              Retake assessment
            </button>
          </div>

          <p className="text-center text-xs text-[#A2B6CB] pb-2">
            For educational use only. Not a substitute for medical advice.
            <br />
            Results are indicative only — always discuss with a qualified clinician.
          </p>
        </div>
      </main>
    </div>
  );
}
