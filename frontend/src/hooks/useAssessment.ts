'use client';

import { useState, useEffect, useCallback } from 'react';
import { resolveQuestionPath, getQuestion } from '@/src/lib/questions';
import { clearStoredMedGemmaResult } from '@/src/lib/medgemma';
import type { Question } from '@/src/lib/questions';

const STORAGE_KEY = 'halffull_assessment_v2';

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

    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      return saved ? (JSON.parse(saved) as AssessmentState) : DEFAULT_STATE;
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
    if (hydrated) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  }, [state, hydrated]);

  // Recalculate path from current answers
  const path = resolveQuestionPath(state.answers);
  const currentIndex = Math.min(state.currentIndex, path.length - 1);
  const currentId = path[currentIndex] ?? '';
  const currentQuestion: Question | undefined = getQuestion(currentId);
  const currentAnswer = currentId ? state.answers[currentId] : undefined;

  const totalQuestions = path.length;
  const progress = totalQuestions > 0 ? ((currentIndex + 1) / totalQuestions) * 100 : 0;
  const isFirst = currentIndex === 0;
  const isLast = currentIndex === path.length - 1;

  // A question is "answered" when it has a non-empty value (unless optional)
  const hasAnswer = useCallback((): boolean => {
    if (!currentQuestion) return false;
    if (currentQuestion.optional) return true;
    const val = state.answers[currentId];
    if (val === undefined || val === null || val === '') return false;
    if (Array.isArray(val) && val.length === 0) return false;
    // dual_numeric: all required sub-fields must be filled (binary required, numeric optional)
    if (currentQuestion.type === 'dual_numeric') {
      const obj = val as Record<string, string>;
      return currentQuestion.options.every((opt) => {
        if ((opt as { sub_type?: string }).sub_type === 'numeric') return true; // optional
        const v = obj[opt.value];
        return v !== undefined && v !== '';
      });
    }
    return true;
  }, [currentQuestion, state.answers, currentId]);

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
      currentIndex: Math.min(prev.currentIndex + 1, path.length - 1),
    }));
  }, [path.length]);

  const goBack = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentIndex: Math.max(prev.currentIndex - 1, 0),
    }));
  }, []);

  const reset = useCallback(() => {
    setState(DEFAULT_STATE);
    localStorage.removeItem(STORAGE_KEY);
    clearStoredMedGemmaResult();
  }, []);

  return {
    currentQuestion,
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
