import assessmentTree from '@/src/data/quiz_nhanes_v2.json';

export type QuestionType =
  | 'binary'
  | 'categorical'
  | 'ordinal'
  | 'numeric'
  | 'dual_numeric'
  | 'multi_select'
  | 'date'
  | 'file_upload'
  | 'free_text';

export type ShownIn = 'full' | 'hybrid';

export interface QuestionOption {
  value: string;
  label: string;
  encoded_value?: number;
  sub_type?: 'binary' | 'numeric';
  help_text?: string;
  unit?: string;
}

export interface Conditional {
  parent_id: string;
  parent_values: string[];
  condition_type: 'equals' | 'contains' | 'range' | 'lab_not_extracted';
}

export interface Question {
  id: string;
  module: string;
  moduleTitle: string;
  text: string;
  help_text?: string;
  type: QuestionType;
  feature_name: string;
  options: QuestionOption[];
  conditional?: Conditional;
  shown_in_paths: ShownIn[];
  optional?: boolean;
}

interface RawQuestion {
  id: string;
  text: string;
  help_text?: string;
  type: QuestionType;
  feature_name: string;
  options: QuestionOption[];
  conditional?: Conditional;
  shown_in_paths?: ShownIn[];
  validation?: {
    required?: boolean;
  };
}

interface RawModule {
  id: string;
  title: string;
  order: number;
  shown_in_paths: ShownIn[];
  questions: RawQuestion[];
}

export const MODULE_LABELS: Record<string, string> = {
  profile: 'About You',
  sleep: 'Sleep',
  activity: 'Activity & Work',
  lifestyle: 'Lifestyle',
  health_history: 'Medical History',
  conditions: 'Health Conditions',
  symptoms: 'Your Symptoms',
  womens_health: "Women's Health",
  labs: 'Recent Labs',
};

export const MODULE_COLORS: Record<string, string> = {
  profile: '#9ea9d3',
  sleep: '#c9d0eb',
  activity: '#7765f4',
  lifestyle: '#b7c2e4',
  health_history: '#9ea9d3',
  conditions: '#c9d0eb',
  symptoms: '#b7c2e4',
  womens_health: '#d7f068',
  labs: '#9ea9d3',
};

const modules = (assessmentTree.assessment.modules as RawModule[]).slice().sort(
  (a, b) => a.order - b.order
);

export const QUESTIONS: Question[] = modules.flatMap((module) =>
  module.questions.map((question) => ({
    id: question.id,
    module: module.id,
    moduleTitle: module.title,
    text: question.text,
    help_text: question.help_text,
    type: question.type,
    feature_name: question.feature_name,
    options: question.options,
    conditional: question.conditional,
    shown_in_paths: question.shown_in_paths ?? module.shown_in_paths,
    optional: question.validation?.required === false,
  }))
);

const QUESTION_MAP: Record<string, Question> = Object.fromEntries(
  QUESTIONS.map((q) => [q.id, q])
);

export function getQuestion(id: string): Question | undefined {
  return QUESTION_MAP[id];
}

function evaluateConditional(
  conditional: Conditional,
  parentQuestion: Question | undefined,
  parentAnswer: unknown
): boolean {
  const { parent_values, condition_type } = conditional;

  // Show manual entry question only when the upload hasn't extracted this field
  if (condition_type === 'lab_not_extracted') {
    const fieldKey = parent_values[0];
    const labAnswer = parentAnswer as { structuredValues?: Record<string, number> } | undefined;
    return !labAnswer?.structuredValues?.[fieldKey];
  }

  if (parentQuestion?.type === 'numeric') {
    const maxThreshold = Math.max(
      ...parent_values.map((value) => {
        const match = value.match(/(\d+)$/);
        return match ? Number.parseInt(match[1], 10) : 0;
      })
    );
    const answer = Number(parentAnswer);
    return answer > 0 && answer <= maxThreshold;
  }

  if (condition_type === 'equals') {
    return parent_values.includes(String(parentAnswer));
  }

  if (Array.isArray(parentAnswer)) {
    return parent_values.some((value) => parentAnswer.includes(value));
  }

  return parent_values.includes(String(parentAnswer));
}

export function resolveQuestionPath(answers: Record<string, unknown>): string[] {
  const isHybrid = answers['q0.0'] === 'lab_yes';
  const activePath: ShownIn = isHybrid ? 'hybrid' : 'full';

  return QUESTIONS.filter((question) => {
    if (!question.shown_in_paths.includes(activePath)) {
      return false;
    }

    if (!question.conditional) {
      return true;
    }

    const parentQuestion = getQuestion(question.conditional.parent_id);
    let parentAnswer = answers[question.conditional.parent_id];
    // If not found at top level, look inside compound (dual_numeric) dict answers
    if (parentAnswer === undefined) {
      for (const val of Object.values(answers)) {
        if (val && typeof val === 'object' && !Array.isArray(val)) {
          const nested = (val as Record<string, unknown>)[question.conditional.parent_id];
          if (nested !== undefined) { parentAnswer = nested; break; }
        }
      }
    }
    return evaluateConditional(question.conditional, parentQuestion, parentAnswer);
  }).map((question) => question.id);
}
