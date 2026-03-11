'use client';

import Link from 'next/link';
import { useAssessment } from '@/src/hooks/useAssessment';

export default function ResultsPage() {
  const { answers, totalQuestions, reset } = useAssessment();
  const answeredCount = Object.keys(answers).length;

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col items-center justify-center px-5 py-12 gap-6">
      {/* Result card */}
      <div className="max-w-lg w-full bg-white rounded-3xl p-8 shadow-[0_4px_24px_rgba(37,70,98,0.08)] flex flex-col gap-5">
        {/* Status */}
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-[#EFB973]/20 flex items-center justify-center mx-auto mb-4">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
              <path
                d="M20 6L9 17l-5-5"
                stroke="#EFB973"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-[#254662]">Assessment complete</h1>
          <p className="text-[#A2B6CB] text-sm mt-2">
            {answeredCount} of {totalQuestions} questions answered
          </p>
        </div>

        {/* Placeholder message */}
        <div className="bg-[#FAF7F2] rounded-2xl p-5">
          <p className="text-[#254662] text-sm leading-relaxed">
            Your answers have been saved to your device. AI-powered fatigue analysis and
            your personalized Doctor Visit Kit will appear here once the backend is connected.
          </p>
        </div>

        {/* What's coming */}
        <div className="flex flex-col gap-2">
          {[
            '🩸 Fatigue driver ranking by signal strength',
            '🧪 Recommended tests for your GP',
            '📋 Personalized doctor visit questions',
            '📄 Exportable doctor-ready PDF report',
          ].map((item) => (
            <div key={item} className="flex items-start gap-2 text-sm text-[#A2B6CB]">
              <span>{item}</span>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 pt-1">
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
            className="w-full py-4 rounded-2xl border-2 border-[#A2B6CB]/40 text-[#254662] font-semibold text-base hover:border-[#254662]/30 transition-all"
          >
            Start over
          </button>
        </div>
      </div>

      <p className="text-xs text-[#A2B6CB] text-center max-w-sm">
        For educational use only. Not a substitute for medical advice.
      </p>
    </div>
  );
}
