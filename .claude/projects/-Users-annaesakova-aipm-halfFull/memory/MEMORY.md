# HalfFull Project Memory

## Project Overview
Fatigue diagnostic web app ("HalfFull"). Frontend assessment flow for a symptom checker that feeds an ML model.

## Repo Structure
- Main repo: `/Users/annaesakova/aipm/halfFull/`
- Frontend: `/Users/annaesakova/aipm/halfFull/frontend/` (Next.js 16, Tailwind v4, TypeScript)
- ML/data scripts: `scripts/`, `notebooks/`, `data/`
- Reference design doc: `/Users/annaesakova/Desktop/HalfFull/lovable-prompt-v2-doctor-one-more-thing (1).md`

## Frontend Architecture
- **IMPORTANT**: Next.js uses `frontend/app/` (NOT `frontend/src/app/`) for routing because both exist
- Components, hooks, lib live in `frontend/src/` and are imported as `@/src/...`
- `@/*` path alias maps to `frontend/` root (see tsconfig.json)
- Tailwind v4 — CSS-first config via `@theme {}` in globals.css (no tailwind.config.ts)
- No `next/font/google` — uses `<link>` tags for Google Fonts (Fraunces + DM Sans) to avoid network issues

## Assessment Flow (built Mar 2026)
Files in `frontend/app/`:
- `app/assessment/page.tsx` — main assessment UI
- `app/results/page.tsx` — results placeholder
- `app/page.tsx` — redirects to /assessment
- `app/layout.tsx` — layout with brand fonts
- `app/globals.css` — design tokens

Files in `frontend/src/`:
- `src/lib/questions.ts` — 26 questions, types, `resolveQuestionPath()` routing logic
- `src/hooks/useAssessment.ts` — state + localStorage (key: `halffull_assessment_v1`)
- `src/components/QuestionCard.tsx` — renders correct input per question type
- `src/components/Answer*.tsx` — AnswerSingle, AnswerMultiple, AnswerScale, AnswerFreeText, AnswerDate, AnswerFileUpload
- `src/components/ProgressBar.tsx`, `NavButtons.tsx`

## Question Routing Logic
- Q0.0=Yes → HYBRID PATH: shows Q0.1 (lab upload), skips Nutrition (Q2.x) + Hormonal (Q3.x)
- Q0.0=No → FULL PATH: all questions
- Activity (Q4.x) and Mental Health (Q5.x) shown on both paths
- Conditional questions: Q1.3 (if sleep quality<5), Q1.5 (if RLS in Q1.4), Q2.3 (if Q2.2=Yes), Q3.2/Q3.3 (if female), Q3.5 (if thyroid diagnosed), Q5.5 (if PHQ-9 score significant)

## Brand Design System
- Background: `#FAF7F2` (warm cream)
- Navy: `#254662` (text, borders)
- Orange: `#EFB973` (CTA, active state)
- Pink: `#EBC7BB` (hormonal module)
- Green: `#C7D9A7` (nutrition module)
- Blue: `#A2B6CB` (sleep module, secondary text)
- Yellow: `#EFD17B` (mental health module)

## How to Run
```
cd /Users/annaesakova/aipm/halfFull/frontend
npm run dev
# → http://localhost:3000  (redirects to /assessment)
```

## Next Steps (not yet built)
- Landing/hero screen (Screen 1 in design doc)
- Results AI analysis (Screen 5)
- Backend: FastAPI + ML model
- Auth: Supabase
- PDF export
