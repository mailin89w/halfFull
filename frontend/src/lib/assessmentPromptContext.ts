import { QUESTIONS, getQuestion, type Question } from '@/src/lib/questions';
import type { LabUploadAnswer } from '@/src/lib/types';

export interface PromptQuestionAnswer {
  questionId: string;
  featureName: string;
  module: string;
  question: string;
  answerLabel: string;
  rawValue: unknown;
}

export interface EvaluatedDisease {
  id: string;
  label: string;
}

export const EVALUATED_FATIGUE_DISEASES: EvaluatedDisease[] = [
  { id: 'perimenopause', label: 'Perimenopause' },
  { id: 'anemia', label: 'Anaemia' },
  { id: 'iron_deficiency', label: 'Iron deficiency' },
  { id: 'kidney', label: 'Kidney disease' },
  { id: 'sleep_disorder', label: 'Sleep disorder' },
  { id: 'thyroid', label: 'Hypothyroidism / thyroid dysfunction' },
  { id: 'hepatitis', label: 'Hepatitis / liver inflammation' },
  { id: 'prediabetes', label: 'Prediabetes' },
  { id: 'inflammation', label: 'Hidden inflammation' },
  { id: 'electrolytes', label: 'Electrolyte imbalance' },
  { id: 'liver', label: 'Liver disease' },
];

function stringifyRawValue(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatSingleAnswer(question: Question, value: unknown): string {
  if (value === null || value === undefined || value === '') return 'No answer recorded';

  if (question.type === 'multi_select' && Array.isArray(value)) {
    const labels = value.map((item) => {
      const match = question.options.find((option) => String(option.value) === String(item));
      return match?.label ?? String(item);
    });
    return labels.length > 0 ? labels.join(', ') : 'No answer recorded';
  }

  if (question.type === 'dual_numeric' && value && typeof value === 'object' && !Array.isArray(value)) {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nestedValue]) => {
        const option = question.options.find((candidate) => candidate.value === key);
        const label = option?.label ?? key;
        return `${label}: ${stringifyRawValue(nestedValue)}`;
      })
      .join(' | ');
  }

  if (question.type === 'file_upload') {
    const upload = value as LabUploadAnswer;
    const structured = upload?.structuredValues
      ? Object.entries(upload.structuredValues)
        .map(([key, numeric]) => `${key}: ${numeric}`)
        .join(' | ')
      : '';
    const extracted = upload?.extractedText?.trim()
      ? upload.extractedText.trim().slice(0, 2000)
      : '';

    if (structured && extracted) {
      return `Structured values: ${structured}\nExtracted lab text:\n${extracted}`;
    }
    if (structured) return `Structured values: ${structured}`;
    if (extracted) return `Extracted lab text:\n${extracted}`;
    return upload?.filename ? `Uploaded file: ${upload.filename}` : 'Lab upload present';
  }

  const option = question.options.find((candidate) => String(candidate.value) === String(value));
  return option?.label ?? stringifyRawValue(value);
}

export function buildAnsweredQuestionMap(answers: Record<string, unknown>): PromptQuestionAnswer[] {
  return QUESTIONS
    .filter((question) => answers[question.id] !== undefined)
    .map((question) => ({
      questionId: question.id,
      featureName: question.feature_name,
      module: question.moduleTitle,
      question: question.text,
      answerLabel: formatSingleAnswer(question, answers[question.id]),
      rawValue: answers[question.id],
    }));
}

export function buildAnsweredQuestionsText(answers: Record<string, unknown>): string {
  const items = buildAnsweredQuestionMap(answers);
  if (items.length === 0) return 'No answered questions available.';

  return items.map((item) => [
    `- ${item.questionId} [${item.featureName}] (${item.module})`,
    `  Question: ${item.question}`,
    `  Answer: ${item.answerLabel}`,
    `  Raw value: ${stringifyRawValue(item.rawValue)}`,
  ].join('\n')).join('\n');
}

export function buildUploadedLabsText(answers: Record<string, unknown>): string {
  const labQuestion = getQuestion('lab_upload');
  const labValue = answers['lab_upload'] as LabUploadAnswer | undefined;
  if (!labQuestion || !labValue) return 'No uploaded lab file provided.';

  const structured = labValue.structuredValues && Object.keys(labValue.structuredValues).length > 0
    ? Object.entries(labValue.structuredValues)
      .map(([key, value]) => {
        const linkedQuestion = QUESTIONS.find((question) => question.feature_name === key || question.id === key);
        const featureName = linkedQuestion?.feature_name ?? key;
        const promptLabel = linkedQuestion?.text ?? key;
        return `- ${featureName}: ${value} (mapped from "${promptLabel}")`;
      })
      .join('\n')
    : 'No structured lab values extracted.';

  const extractedText = labValue.extractedText?.trim()
    ? labValue.extractedText.trim().slice(0, 4000)
    : 'No raw extracted lab text available.';

  return [
    `Question: ${labQuestion.text}`,
    `Feature name: ${labQuestion.feature_name}`,
    `Filename: ${labValue.filename || 'unknown file'}`,
    'Structured lab values before normalization:',
    structured,
    'Raw extracted lab text:',
    extractedText,
  ].join('\n');
}
