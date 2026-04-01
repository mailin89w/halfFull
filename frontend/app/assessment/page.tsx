'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAssessment } from '@/src/hooks/useAssessment';
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
    currentValidationErrors,
    setAnswer,
    goNext,
    goBack,
    reset,
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

  const handleRestart = () => {
    reset();
    router.replace('/assessment');
  };

  return (
    <div className="phone-frame flex flex-col">
      <header className="px-5 pt-6 pb-5">
        <div className="mx-auto max-w-lg">
          <div className="mb-5 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">
            <Link href="/start" aria-label="Go to start page">
              <span style={{ fontFamily: 'Archivo, sans-serif', letterSpacing: '-0.02em', textTransform: 'none', fontSize: 16, lineHeight: 1 }}><span style={{ fontWeight: 400, color: 'var(--color-ink-soft)' }}>half</span><span style={{ fontWeight: 900, color: 'var(--color-ink)' }}>Full</span></span>
            </Link>
            <button
              type="button"
              onClick={handleRestart}
              className="text-[var(--color-ink-soft)]"
            >
              Restart
            </button>
          </div>

          <ProgressBar
            progress={progress}
            currentIndex={currentIndex}
            total={totalQuestions}
            modules={chapterModules}
            currentModuleTitle={currentQuestion?.moduleTitle}
          />
        </div>
      </header>

      <main className="flex-1 px-5 py-4 overflow-y-auto">
        <div className="max-w-lg mx-auto">
          {currentQuestions.length > 1 || Boolean(currentQuestion.screen_group) ? (
            <QuestionGroupCard
              questions={currentQuestions}
              answers={answers}
              errors={currentValidationErrors}
              onAnswer={setAnswer}
            />
          ) : (
            <QuestionCard
              question={currentQuestion}
              value={currentAnswer}
              error={currentQuestion ? currentValidationErrors[currentQuestion.id] : null}
              onChange={(val) => setAnswer(currentQuestion.id, val)}
              answers={answers}
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
          {!hasAnswer && (
            <p className="text-center text-[11px] leading-4 text-[var(--color-ink-soft)]">
              Please answer the question above to proceed.
            </p>
          )}
        </div>
      </footer>
    </div>
  );
}
