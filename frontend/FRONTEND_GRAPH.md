# Frontend Connection Graph

This graph shows how the main pieces in `frontend/` connect today.

## Main Runtime Graph

```mermaid
flowchart TD
    Root["app/layout.tsx\nRoot layout + global fonts/styles"] --> Home["app/page.tsx\nredirect('/start')"]
    Home --> Start["app/start/page.tsx\nLanding page"]
    Start --> Assessment["app/assessment/page.tsx\nMain questionnaire UI"]
    Assessment --> Clarify["app/clarify/page.tsx\nAI follow-up questions"]
    Clarify --> Processing["app/processing/page.tsx\nRun AI analysis"]
    Processing --> Results["app/results/page.tsx\nFinal report + doctor kit"]

    Assessment --> UseAssessment["src/hooks/useAssessment.ts\nassessment state + localStorage"]
    Clarify --> UseAssessment
    Processing --> UseAssessment
    Results --> UseAssessment

    UseAssessment --> QuestionsLib["src/lib/questions.ts\nquestion registry + branching"]
    QuestionsLib --> TreeJson["src/data/Assessment_Tree_Complete_Example_FINAL.json\nassessment content"]

    Assessment --> QuestionCard["src/components/QuestionCard.tsx"]
    Assessment --> ProgressBar["src/components/ProgressBar.tsx"]
    Assessment --> NavButtons["src/components/NavButtons.tsx"]

    QuestionCard --> AnswerSingle["src/components/AnswerSingle.tsx"]
    QuestionCard --> AnswerMultiple["src/components/AnswerMultiple.tsx"]
    QuestionCard --> AnswerScale["src/components/AnswerScale.tsx"]
    QuestionCard --> AnswerDate["src/components/AnswerDate.tsx"]
    QuestionCard --> AnswerFreeText["src/components/AnswerFreeText.tsx"]
    QuestionCard --> AnswerFileUpload["src/components/AnswerFileUpload.tsx"]

    AnswerFileUpload --> ExtractLabs["app/api/extract-labs/route.ts\nextract uploaded lab text"]

    Clarify --> MockResults["src/lib/mockResults.ts\nrule-based diagnosis shortlist"]
    Clarify --> MedGemma["src/lib/medgemma.ts\nsession cache + fetch helpers"]
    Clarify --> FollowupAPI["app/api/generate-followup/route.ts"]
    Clarify --> Blob["src/components/ui/BlobCharacter.tsx"]

    Processing --> MockResults
    Processing --> MedGemma
    Processing --> DeepAnalyze["app/api/deep-analyze/route.ts"]
    Processing --> Analyze["app/api/analyze/route.ts\nfallback insights"]
    Processing --> Blob

    Results --> MockResults
    Results --> MedGemma
    Results --> Energy["src/components/results/EnergySpectrum.tsx"]
    Results --> Diagnosis["src/components/results/DiagnosisCard.tsx"]
    Results --> Doctor["src/components/results/DoctorPriority.tsx"]
    Results --> Blob

    Analyze --> FormatAnswers["src/lib/formatAnswers.ts\nserialize answers for prompts"]
    DeepAnalyze --> FormatAnswers
    FollowupAPI --> FormatAnswers
```

## Data Flow

```mermaid
flowchart LR
    User["User answers"] --> AssessmentState["useAssessment\nlocalStorage: halffull_assessment_v1"]
    AssessmentState --> Path["resolveQuestionPath()"]
    Path --> UI["QuestionCard + answer components"]

    AssessmentState --> ClarifyAnswers["clarify_* answers"]
    AssessmentState --> RuleEngine["computeResults()"]

    RuleEngine --> FollowUpFetch["fetchFollowUpQuestions()"]
    FollowUpFetch --> FollowUpAPI["/api/generate-followup"]
    FollowUpAPI --> HF["HuggingFace / MedGemma"]
    HF --> FollowUpCache["sessionStorage: halffull_followup_v1"]

    RuleEngine --> DeepFetch["fetchDeepAnalysis()"]
    DeepFetch --> DeepAPI["/api/deep-analyze"]
    DeepAPI --> HF
    HF --> DeepCache["sessionStorage: halffull_deep_v1"]

    DeepFetch --> BasicFallback["fetchMedGemmaInsights()"]
    BasicFallback --> AnalyzeAPI["/api/analyze"]
    AnalyzeAPI --> HF
    HF --> BasicCache["sessionStorage: halffull_medgemma_v1"]

    DeepCache --> Results["results page"]
    RuleEngine --> Results
```

## File Roles

- `frontend/app/*`: active App Router pages and API routes.
- `frontend/src/hooks/useAssessment.ts`: shared assessment state, localStorage persistence, path recalculation, reset.
- `frontend/src/lib/questions.ts`: turns the assessment tree JSON into runtime questions and branching logic.
- `frontend/src/lib/mockResults.ts`: current rule-based scoring and doctor recommendations used before / alongside backend ML.
- `frontend/src/lib/medgemma.ts`: fetch helpers and session-storage caching for AI outputs.
- `frontend/src/lib/formatAnswers.ts`: common serializer used by the API routes to turn raw answers into prompt text.
- `frontend/src/components/*`: reusable input and presentation components.
- `frontend/src/components/results/*`: result-specific cards and visual summaries.
- `frontend/src/data/Assessment_Tree_Complete_Example_FINAL.json`: question content source consumed by `questions.ts`.

## Important Structural Note

- There are duplicate route files under both `frontend/app/` and `frontend/src/app/`.
- The active Next.js App Router entrypoint is `frontend/app/`.
- `frontend/src/app/` looks like an older parallel copy or prototype layer and is not the primary runtime path if `frontend/app/` is being served.
