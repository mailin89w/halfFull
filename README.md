# halfFull
# HalfFull: AI-Powered Fatigue Analysis

HalfFull is a privacy-first tool I’m building to help people figure out what’s actually causing their chronic fatigue. Instead of getting lost in a generic chat, the app connects personal symptoms with real medical data (NHANES) to give users a solid foundation for their next doctor's appointment.

---

## Project Roadmap

### Epic 1: Setup and Data Engineering (Week 1)
Focus: Getting the data right and setting up the environment.
- Subtask 1.1: Project Infrastructure - Setting up the GitHub repo, initializing Next.js, and connecting Vercel for CI/CD.
- Subtask 1.2: NHANES Dataset Integration - Cleaning the labs.csv and mapping biomarkers like Ferritin, B12, and TSH to proper reference ranges.
- Subtask 1.3: Core Scoring Engine - Building the logic that actually compares user inputs against NHANES population data.

### Epic 2: Assessment Engine and MVP (Week 1)
Focus: Building the first functional version of the "Decision Tree."
- Subtask 2.1: Static Decision Tree (JSON) - Creating the structure for the 5 main modules: Sleep, Nutrition, Hormones, Activity, and Mental Health.
- Subtask 2.2: One-Question-Per-Screen UI - Building the frontend with a progress bar and making sure answers stay saved in LocalStorage.
- Subtask 2.3: Results Dashboard v1 - Making sure the first Energy Score and the main fatigue drivers show up correctly.

### Epic 3: Intelligence Layer (Week 2)
Focus: Bringing in the AI to make the app smarter.
- Subtask 3.1: Medical-Llama3 Integration - Connecting the local AI server (LM Studio) to the Next.js API.
- Subtask 3.2: Adaptive Follow-up Logic - Adding "LLM-nodes" so the app can ask smart, dynamic questions based on what the user just answered.
- Subtask 3.3: RAG Evidence Store - Linking medical sources so every insight the AI gives is backed by a real citation.

### Epic 4: UI/UX Polish and Reporting (Week 3)
Focus: Making it look great and preparing the final output.
- Subtask 4.1: Design System Implementation - Applying the final look, including typography (Fraunces, DM Sans) and the HalfFull branding.
- Subtask 4.2: Doctor-Ready PDF Export - Creating the final summary that users can actually take to their doctor.
- Subtask 4.3: PWA and Accessibility - Making sure it works perfectly on mobile and follows accessibility standards.

---

## Technical Concept: The Assessment Tree

I decided to go with a hybrid approach for HalfFull to keep things medically accurate but still easy to use.

1. Structured Backbone: A JSON-based tree makes sure we don't miss any important clinical areas.
2. AI Augmentation: Medical-Llama3 jumps in when it hears something interesting and asks deeper, adaptive questions.
3. Deterministic Scoring: While the conversation is fluid, the actual scoring stays tied to the NHANES data. This prevents the AI from "hallucinating" medical results.

---

## Tech Stack
- Frontend: Next.js, Tailwind CSS, Framer Motion
- AI/ML: Medical-Llama3-8B, RAG (Retrieval-Augmented Generation)
- Data: NHANES (National Health and Nutrition Examination Survey)
- Deployment: Vercel

## Python Environment Setup

### Windows (PowerShell)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas pyreadstat jupyter ipykernel
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas pyreadstat jupyter ipykernel
```

## Frontend Setup

cd frontend
npm install
npm run dev

and then open:
http://localhost:3000