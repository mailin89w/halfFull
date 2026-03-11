# HalfFull — Frontend

Energy assessment interface built with **Next.js 16**, **React 19**, and **Tailwind CSS v4**.

---

## What you'll see

The app is a two-screen flow:

| Route | Description |
|---|---|
| `/assessment` | Step-by-step questionnaire (20 questions on the full path, 14 on the hybrid path) |
| `/results` | Personalised energy report with an energy spectrum, diagnosis cards, and doctor priority recommendations |

The root `/` redirects straight to `/assessment`.

Progress is stored in **localStorage** under the key `halffull_assessment_v1`, so the browser remembers where you left off on refresh.

---

## Running locally

**Requirements:** Node ≥ 18

```bash
# 1. From the repo root, go into the frontend folder
cd frontend

# 2. Install dependencies (first time only)
npm install

# 3. Start the dev server
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** — the assessment starts immediately.

---

## Other scripts

```bash
npm run build   # Production build
npm run start   # Serve the production build (run build first)
npm run lint    # ESLint check
```

---

## Key files

```
frontend/
├── src/
│   ├── app/
│   │   ├── assessment/page.tsx   # Assessment screen
│   │   └── results/page.tsx      # Results screen
│   ├── components/
│   │   ├── QuestionCard.tsx      # Renders a single question
│   │   ├── AnswerSingle.tsx      # Binary / categorical / ordinal options
│   │   ├── AnswerMultiple.tsx    # Multi-select checkboxes
│   │   ├── AnswerScale.tsx       # 1–10 numeric scale
│   │   ├── AnswerDate.tsx        # Date picker
│   │   ├── AnswerFreeText.tsx    # Open text input
│   │   └── results/
│   │       ├── EnergySpectrum.tsx   # Vertical bar "where you are vs potential"
│   │       ├── DiagnosisCard.tsx    # Per-area diagnosis with recommendations
│   │       └── DoctorPriority.tsx   # Prioritised list of areas to raise with a doctor
│   └── lib/
│       ├── questions.ts          # All 26 questions + conditional routing logic
│       └── mockResults.ts        # Derives results from stored answers
```

---

## How the assessment paths work

The very first question (`q0.0`) asks whether the user has recent lab results:

- **Lab results available (`lab_yes`)** → **Hybrid path** — 14 questions (skips nutrition and hormonal modules since labs cover them)
- **No lab results (`lab_no`)** → **Full path** — 20 questions (all modules)

Several questions are conditional and only appear based on earlier answers (e.g. the RLS follow-up only shows if restless legs was selected in the sleep issues question).
