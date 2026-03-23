// ─── Shared types used across multiple modules ────────────────────────────────

/** Stored in answers['lab_upload'] after lab file extraction */
export interface LabUploadAnswer {
  filename: string;
  extractedText: string; // MedGemma-extracted lab text, ≤4000 chars
  status: 'extracting' | 'done' | 'error';
  errorMessage?: string;
  /** Parsed numeric values keyed by quiz field ID (e.g. total_cholesterol_mg_dl) */
  structuredValues?: Record<string, number>;
}

/** Response from /api/generate-followup */
export interface FollowUpResult {
  hypotheses: string[]; // 2-3 diagnostic hypotheses
  questions: string[]; // exactly 3 follow-up questions
}

/** Response from /api/deep-analyze */
export interface DeepAnalysisResult {
  textSummary: string;
  doctorRecommendations: Array<{
    specialty: string;
    reason: string;
    urgency: 'immediate' | 'soon' | 'when_available';
  }>;
  additionalTests: Array<{
    name: string;
    why: string;
    mustRequest: boolean;
  }>;
  doctorKit: {
    openingStatement: string;
    symptomTimeline: string;
    keyQuestions: string[];
    redFlags: string[];
  };
  coachingTips: Array<{
    category: string;
    tip: string;
    timeframe: string;
  }>;
}

/** A single message in the follow-up chatbot conversation */
export interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  questionIndex?: number; // 0, 1, or 2
}

/** Persisted state for the /chat page (localStorage: halffull_chat_v1) */
export interface ChatState {
  hypotheses: string[];
  followUpQuestions: string[];
  chatTranscript: ChatMessage[];
  roundsCompleted: number; // 0-3
  skipped: boolean;
}
