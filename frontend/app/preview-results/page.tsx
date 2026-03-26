'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { createMockDeepResult } from '@/src/lib/medgemma';
import {
  ASSESSMENT_STORAGE_KEY,
  BAYESIAN_ANSWERS_KEY,
  BAYESIAN_DETAILS_KEY,
  BAYESIAN_SCORES_KEY,
  CONFIRMED_CONDITIONS_KEY,
  DEEP_STORAGE_KEY,
  ML_SCORES_KEY,
} from '@/src/lib/privacy';

const DEMO_ANSWERS = {
  gender: '2',
  age: '44',
  q0: 'demo',
  lab_upload: {
    filename: 'demo-labs.pdf',
    extractedText: [
      'Ferritin 9 ng/mL [LOW]',
      'Hemoglobin 10.4 g/dL [LOW]',
      'TSH 5.6 mIU/L [HIGH]',
      'HbA1c 5.9 % [HIGH]',
      'ALT 32 U/L',
    ].join('\n'),
    status: 'done',
    structuredValues: {
      fasting_glucose_mg_dl: 109,
      glucose_mg_dl: 118,
    },
  },
};

const DEMO_ML_SCORES = {
  anemia: 0.71,
  iron_deficiency: 0.69,
  thyroid: 0.58,
  prediabetes: 0.49,
  sleep_disorder: 0.42,
};

const DEMO_BAYESIAN_SCORES = {
  anemia: 0.83,
  iron_deficiency: 0.79,
  thyroid: 0.62,
  prediabetes: 0.55,
  sleep_disorder: 0.39,
};

const DEMO_BAYESIAN_DETAILS = {
  anemia: {
    condition: 'anemia',
    prior: 0.71,
    posterior: 0.83,
    lrs_applied: [
      {
        question_id: 'anemia_q1',
        answer: 'yes',
        answerLabel: 'Yes',
        questionText: 'Are your periods heavier than they used to be?',
        lr: 2.4,
      },
      {
        question_id: 'anemia_q4',
        answer: 'yes',
        answerLabel: 'Yes',
        questionText: 'Do you often feel unusually cold?',
        lr: 1.8,
      },
    ],
    questions_used: ['anemia_q1', 'anemia_q4'],
    confounder_mult: 1,
    clipped: false,
  },
  iron_deficiency: {
    condition: 'iron_deficiency',
    prior: 0.69,
    posterior: 0.79,
    lrs_applied: [
      {
        question_id: 'iron_q1',
        answer: 'yes',
        answerLabel: 'Yes',
        questionText: 'Have you had heavier bleeding recently?',
        lr: 3.5,
      },
    ],
    questions_used: ['iron_q1'],
    confounder_mult: 1,
    clipped: false,
  },
  thyroid: {
    condition: 'thyroid',
    prior: 0.58,
    posterior: 0.62,
    lrs_applied: [
      {
        question_id: 'thyroid_q1',
        answer: 'yes',
        answerLabel: 'Yes',
        questionText: 'Have you noticed cold intolerance?',
        lr: 1.6,
      },
    ],
    questions_used: ['thyroid_q1'],
    confounder_mult: 1,
    clipped: false,
  },
};

export default function PreviewResultsPage() {
  const router = useRouter();

  useEffect(() => {
    const deep = createMockDeepResult(DEMO_ANSWERS);
    deep.knnSignals = {
      lab_signals: [
        {
          lab: 'low ferritin',
          direction: 'low',
          neighbour_pct: 68,
          lift: 2.4,
          ref_lower: 20,
          ref_upper: 150,
          context: 'common in similar fatigue profiles',
        },
        {
          lab: 'low hemoglobin',
          direction: 'low',
          neighbour_pct: 61,
          lift: 1.9,
          ref_lower: 12,
          ref_upper: 15.5,
          context: 'supports anemia pattern',
        },
      ],
      n_signals: 2,
      k_neighbours: 50,
    };

    window.sessionStorage.setItem(
      ASSESSMENT_STORAGE_KEY,
      JSON.stringify({
        updatedAt: new Date().toISOString(),
        value: {
          answers: DEMO_ANSWERS,
          currentIndex: 0,
        },
      })
    );
    window.sessionStorage.setItem(ML_SCORES_KEY, JSON.stringify(DEMO_ML_SCORES));
    window.sessionStorage.setItem(BAYESIAN_SCORES_KEY, JSON.stringify(DEMO_BAYESIAN_SCORES));
    window.sessionStorage.setItem(BAYESIAN_DETAILS_KEY, JSON.stringify(DEMO_BAYESIAN_DETAILS));
    window.sessionStorage.setItem(
      BAYESIAN_ANSWERS_KEY,
      JSON.stringify([
        {
          group: 'Anaemia · 71%',
          question: 'Are your periods heavier than they used to be?',
          answer: 'Yes',
        },
        {
          group: 'Anaemia · 71%',
          question: 'Do you often feel unusually cold?',
          answer: 'Yes',
        },
      ])
    );
    window.sessionStorage.setItem(CONFIRMED_CONDITIONS_KEY, JSON.stringify([]));
    window.sessionStorage.setItem(DEEP_STORAGE_KEY, JSON.stringify(deep));

    router.replace('/results');
  }, [router]);

  return (
    <div className="phone-frame flex items-center justify-center">
      <p className="text-sm text-[var(--color-ink-soft)]">Loading preview…</p>
    </div>
  );
}
