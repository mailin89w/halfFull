'use client';

import Link from 'next/link';
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
      <div className="phone-frame flex items-center justify-center">
        <div className="text-[var(--color-ink-soft)] text-sm">Loading...</div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="phone-frame flex items-center justify-center">
        <p className="text-[var(--color-ink)]">No questions available.</p>
      </div>
    );
  }

  const handleNext = () => {
    if (isLast) {
      router.push('/clarify');
    } else {
      goNext();
    }
  };

  return (
    <div className="phone-frame flex flex-col">
      <header className="px-5 pt-6 pb-5">
        <div className="mx-auto max-w-lg">
          <div className="mb-5 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <span>HalfFull</span>
            <Link href="/start" className="text-[var(--color-ink-soft)]">
              Start
            </Link>
          </div>

          <ProgressBar progress={progress} currentIndex={currentIndex} total={totalQuestions} />
        </div>
      </header>

      <main className="flex-1 px-5 py-4 overflow-y-auto">
        <div className="max-w-lg mx-auto">
          <QuestionCard
            question={currentQuestion}
            value={currentAnswer}
            onChange={(val) => setAnswer(currentQuestion.id, val)}
          />
        </div>
      </main>

      <footer className="px-5 pt-4 pb-8">
        <div className="max-w-lg mx-auto space-y-3">
          <NavButtons
            isFirst={isFirst}
            isLast={isLast}
            canAdvance={hasAnswer}
            onBack={goBack}
            onNext={handleNext}
          />
          <p className="text-center text-[11px] leading-4 text-[var(--color-ink-soft)]">
            For educational use only. Not a substitute for medical advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
