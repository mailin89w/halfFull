'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAssessment } from '@/src/hooks/useAssessment';
import { ExitAssessmentButton } from '@/src/components/ExitAssessmentButton';
import { QuestionCard } from '@/src/components/QuestionCard';
import { QuestionGroupCard } from '@/src/components/QuestionGroupCard';
import { ProgressBar } from '@/src/components/ProgressBar';
import type { ChapterModule } from '@/src/components/ProgressBar';
import { NavButtons } from '@/src/components/NavButtons';
import { QUESTIONS, MODULE_LABELS } from '@/src/lib/questions';

export default function AssessmentPage() {
  const router = useRouter();
  const {
    currentQuestion,
    currentQuestions,
    currentAnswer,
    currentIndex,
    totalQuestions,
    progress,
    path,
    isFirst,
    isLast,
    hasAnswer,
    hydrated,
    answers,
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

  // Build ordered module chapter list from the active path
  const pathModuleIds = [...new Set(
    path
      .map((id) => QUESTIONS.find((q) => q.id === id)?.module)
      .filter((m): m is string => Boolean(m))
  )];
  const currentModuleId = currentQuestion?.module ?? '';
  const currentModuleIndex = pathModuleIds.indexOf(currentModuleId);
  const chapterModules: ChapterModule[] = pathModuleIds.map((mid, i) => ({
    id: mid,
    title: MODULE_LABELS[mid] ?? mid,
    state: i < currentModuleIndex ? 'done' : i === currentModuleIndex ? 'active' : 'upcoming',
  }));

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
            <div className="flex items-center gap-3">
              <ExitAssessmentButton
                className="text-[var(--color-ink-soft)]"
                label="Exit"
              />
              <Link href="/start" className="text-[var(--color-ink-soft)]">
                Start
              </Link>
            </div>
          </div>

          <ProgressBar
            progress={progress}
            currentIndex={currentIndex}
            total={totalQuestions}
            modules={chapterModules}
            currentModuleTitle={currentQuestion?.moduleTitle}
            currentModuleIndex={currentModuleIndex}
          />
        </div>
      </header>

      <main className="flex-1 px-5 py-4 overflow-y-auto">
        <div className="max-w-lg mx-auto">
          {currentQuestions.length > 1 ? (
            <QuestionGroupCard
              questions={currentQuestions}
              answers={answers}
              onAnswer={setAnswer}
            />
          ) : (
            <QuestionCard
              question={currentQuestion}
              value={currentAnswer}
              onChange={(val) => setAnswer(currentQuestion.id, val)}
            />
          )}
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
