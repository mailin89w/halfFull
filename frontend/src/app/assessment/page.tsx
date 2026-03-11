'use client';

import { useRouter } from 'next/navigation';
import { useAssessment } from '@/src/hooks/useAssessment';
import { QuestionCard } from '@/src/components/QuestionCard';
import { ProgressBar } from '@/src/components/ProgressBar';
import { NavButtons } from '@/src/components/NavButtons';

export default function AssessmentPage() {
  const router = useRouter();
  const {
    currentQuestion,
    currentAnswer,
    currentIndex,
    totalQuestions,
    progress,
    isFirst,
    isLast,
    hasAnswer,
    hydrated,
    setAnswer,
    goNext,
    goBack,
  } = useAssessment();

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center">
        <div className="text-[#A2B6CB] text-sm">Loading…</div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center">
        <p className="text-[#254662]">No questions available.</p>
      </div>
    );
  }

  const handleNext = () => {
    if (isLast) {
      router.push('/results');
    } else {
      goNext();
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col">
      {/* Header */}
      <header className="px-5 pt-6 pb-4">
        <div className="max-w-lg mx-auto space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-[#254662] font-semibold text-lg tracking-tight">
              HalfFull
            </span>
            <span className="text-xs text-[#A2B6CB]">🔒 Data stays on your device</span>
          </div>
          <ProgressBar
            progress={progress}
            currentIndex={currentIndex}
            total={totalQuestions}
          />
        </div>
      </header>

      {/* Main question area */}
      <main className="flex-1 px-5 py-4 overflow-y-auto">
        <div className="max-w-lg mx-auto">
          <QuestionCard
            question={currentQuestion}
            value={currentAnswer}
            onChange={(val) => setAnswer(currentQuestion.id, val)}
          />
        </div>
      </main>

      {/* Navigation */}
      <footer className="px-5 pt-4 pb-8">
        <div className="max-w-lg mx-auto space-y-3">
          <NavButtons
            isFirst={isFirst}
            isLast={isLast}
            canAdvance={hasAnswer}
            onBack={goBack}
            onNext={handleNext}
          />
          <p className="text-center text-xs text-[#A2B6CB]">
            For educational use only. Not a substitute for medical advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
