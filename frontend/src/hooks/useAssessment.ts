'use client';

import { useState, useEffect, useCallback } from 'react';
import { resolveQuestionPath, getQuestion, getScreens } from '@/src/lib/questions';
import { clearStoredMedGemmaResult } from '@/src/lib/medgemma';
import {
  ASSESSMENT_STORAGE_KEY,
  clearExpiredHealthData,
  unwrapPersistedHealthData,
  wrapPersistedHealthData,
} from '@/src/lib/privacy';
import type { Question } from '@/src/lib/questions';

interface AssessmentState {
  answers: Record<string, unknown>;
  currentIndex: number;
}

const DEFAULT_STATE: AssessmentState = {
  answers: {},
  currentIndex: 0,
};

export function useAssessment() {
  const [state, setState] = useState<AssessmentState>(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_STATE;
    }

    clearExpiredHealthData();
    try {
      const saved = window.sessionStorage.getItem(ASSESSMENT_STORAGE_KEY);
      return unwrapPersistedHealthData<AssessmentState>(saved) ?? DEFAULT_STATE;
    } catch {
      return DEFAULT_STATE;
    }
  });
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setHydrated(true);
    });

    return () => window.cancelAnimationFrame(frame);
  }, []);

  // Persist to localStorage on every change
  useEffect(() => {
    if (!hydrated) return;
    window.sessionStorage.setItem(
      ASSESSMENT_STORAGE_KEY,
      JSON.stringify(wrapPersistedHealthData(state))
    );
  }, [state, hydrated]);

  // Recalculate path and screens from current answers
  const path = resolveQuestionPath(state.answers);
  const screens = getScreens(path);
  const currentIndex = Math.min(state.currentIndex, screens.length - 1);
  const currentScreenIds = screens[currentIndex] ?? [];
  const currentQuestions = currentScreenIds
    .map((id) => getQuestion(id))
    .filter((q): q is Question => q !== undefined);
  const currentQuestion: Question | undefined = currentQuestions[0];
  const currentId = currentQuestion?.id ?? '';
  const currentAnswer = currentId ? state.answers[currentId] : undefined;

  const totalQuestions = screens.length;
  const progress = totalQuestions > 0 ? ((currentIndex + 1) / totalQuestions) * 100 : 0;
  const isFirst = currentIndex === 0;
  const isLast = currentIndex === screens.length - 1;

  // All visible questions in the current screen must be answered (unless optional)
  const hasAnswer = useCallback((): boolean => {
    if (currentQuestions.length === 0) return false;
    return currentQuestions.every((q) => {
      if (q.optional) return true;
      const val = state.answers[q.id];
      if (val === undefined || val === null || val === '') return false;
      if (Array.isArray(val) && val.length === 0) return false;
      if (q.type === 'dual_numeric') {
        const obj = val as Record<string, string>;
        return q.options.every((opt) => {
          if ((opt as { sub_type?: string }).sub_type === 'numeric') return true;
          const v = obj[opt.value];
          return v !== undefined && v !== '';
        });
      }
      return true;
    });
  }, [currentQuestions, state.answers]);

  const setAnswer = useCallback((questionId: string, value: unknown) => {
    setState((prev) => {
      const newAnswers = { ...prev.answers, [questionId]: value };

      // Recalculate path and prune answers that no longer belong
      const newPath = resolveQuestionPath(newAnswers);
      const pathSet = new Set(newPath);
      const pruned: Record<string, unknown> = {};
      for (const id of Object.keys(newAnswers)) {
        if (pathSet.has(id)) pruned[id] = newAnswers[id];
      }

      return { ...prev, answers: pruned };
    });
  }, []);

  const goNext = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentIndex: Math.min(prev.currentIndex + 1, screens.length - 1),
    }));
  }, [screens.length]);

  const goBack = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentIndex: Math.max(prev.currentIndex - 1, 0),
    }));
  }, []);

  const reset = useCallback(() => {
    setState(DEFAULT_STATE);
    window.sessionStorage.removeItem(ASSESSMENT_STORAGE_KEY);
    clearStoredMedGemmaResult();
  }, []);

  return {
    currentQuestion,
    currentQuestions,
    currentAnswer,
    currentIndex,
    totalQuestions,
    progress,
    path,
    isFirst,
    isLast,
    hasAnswer: hasAnswer(),
    hydrated,
    answers: state.answers,
    setAnswer,
    goNext,
    goBack,
    reset,
  };
}
