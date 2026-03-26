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

type ValidationError = string | Record<string, string>;

interface AssessmentState {
  answers: Record<string, unknown>;
  currentIndex: number;
}

const DEFAULT_STATE: AssessmentState = {
  answers: {},
  currentIndex: 0,
};

function deriveBodyMetrics(answers: Record<string, unknown>): Record<string, unknown> {
  const nextAnswers = { ...answers };
  const height = parseFloat(String(nextAnswers.height_cm ?? ''));
  const weight = parseFloat(String(nextAnswers.weight_kg ?? ''));

  if (Number.isFinite(height) && Number.isFinite(weight) && height > 0 && weight > 0) {
    nextAnswers.bmi = (weight / (height / 100) ** 2).toFixed(1);
  } else {
    delete nextAnswers.bmi;
  }

  return nextAnswers;
}

function formatRangeError(label: string, min?: number, max?: number): string {
  if (min !== undefined && max !== undefined) {
    return `Please enter ${label.toLowerCase()} between ${min} and ${max}.`;
  }
  if (min !== undefined) {
    return `Please enter ${label.toLowerCase()} of at least ${min}.`;
  }
  return `Please enter ${label.toLowerCase()} of ${max} or less.`;
}

function getValidationError(question: Question, value: unknown): ValidationError | null {
  if (value === undefined || value === null || value === '') return null;

  const min = question.validation?.min;
  const max = question.validation?.max;

  if (question.type === 'numeric') {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return null;
    if (min !== undefined && parsed < min) return formatRangeError(question.options[0]?.label ?? question.text, min, max);
    if (max !== undefined && parsed > max) return formatRangeError(question.options[0]?.label ?? question.text, min, max);
  }

  if (question.type === 'dual_numeric') {
    const raw = value as Record<string, string>;
    const fieldErrors: Record<string, string> = {};

    for (const option of question.options) {
      if (option.sub_type === 'binary') continue;
      const fieldValue = raw[option.value];
      if (fieldValue === undefined || fieldValue === '') continue;
      const parsed = Number(fieldValue);
      if (!Number.isFinite(parsed)) continue;

      const fieldMin = option.min ?? min;
      const fieldMax = option.max ?? max;
      if (fieldMin !== undefined && parsed < fieldMin) {
        fieldErrors[option.value] = formatRangeError(option.label, fieldMin, fieldMax);
      } else if (fieldMax !== undefined && parsed > fieldMax) {
        fieldErrors[option.value] = formatRangeError(option.label, fieldMin, fieldMax);
      }
    }

    return Object.keys(fieldErrors).length > 0 ? fieldErrors : null;
  }

  return null;
}

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
  const currentValidationErrors = Object.fromEntries(
    currentQuestions
      .map((q) => [q.id, getValidationError(q, state.answers[q.id])] as const)
      .filter(([, error]) => Boolean(error))
  ) as Record<string, ValidationError>;

  // All visible questions in the current screen must be answered (unless optional)
  const hasAnswer = useCallback((): boolean => {
    if (currentQuestions.length === 0) return false;
    return currentQuestions.every((q) => {
      const val = state.answers[q.id];
      if (q.optional && (val === undefined || val === null || val === '')) {
        return true;
      }
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
        if (currentValidationErrors[q.id]) return false;
        return true;
      });
  }, [currentQuestions, currentValidationErrors, state.answers]);

  const setAnswer = useCallback((questionId: string, value: unknown) => {
    setState((prev) => {
      clearStoredMedGemmaResult();
      const newAnswers = deriveBodyMetrics({ ...prev.answers, [questionId]: value });

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
    currentValidationErrors,
    setAnswer,
    goNext,
    goBack,
    reset,
  };
}
