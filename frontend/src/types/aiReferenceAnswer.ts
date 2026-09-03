/**
 * Types mirroring the backend's AI Reference Answer Builder milestone
 * Pydantic schemas (`backend/app/schemas/ai_reference_answer.py`)
 * field-for-field — same snake_case/Decimal-as-string convention as
 * `types/officialExam.ts` (see its file-level comment). Kept in its own
 * file rather than folded into `officialExam.ts` since it's a
 * substantial, independently-versioned entity (see the backend model's
 * module docstring for the full design rationale).
 */

export type AIReferenceAnswerStatus =
  | "queued"
  | "generating"
  | "generation_failed"
  | "pending_verification"
  | "approved"
  | "rejected";

/** The AI-synthesized structure around the official model answer — the
 * official answer is never replaced, only expanded around (see the
 * backend model's "CRITICAL PRINCIPLE" docstring). Every list may be
 * genuinely empty; a provider that can't confidently produce a given
 * list must leave it empty rather than fabricate entries. */
export interface AIReferenceStructuredContent {
  required_concepts: string[];
  optional_concepts: string[];
  keywords: string[];
  equivalent_terms: string[];
  alternative_valid_answers: string[];
  expected_reasoning: string[];
  common_misconceptions: string[];
  scoring_guidance: string[];
}

export interface AIReferenceAnswer {
  id: string;
  institution_id: string;
  extracted_question_id: string;
  extracted_model_answer_id: string | null;
  rubric_id: string | null;
  ai_provider_id: string;
  version: number;
  is_current: boolean;
  status: AIReferenceAnswerStatus;
  question_text: string;
  official_model_answer_text: string;
  synthesized_reference_answer: string | null;
  structured_content: AIReferenceStructuredContent | null;
  maximum_marks: string;
  marks_source: string;
  provider_model: string | null;
  prompt_version: string | null;
  generation_confidence: string | null;
  generation_error: string | null;
  has_conflict_flag: boolean;
  conflict_notes: string | null;
  rejection_reason: string | null;
  generated_at: string | null;
  verified_by: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Request body for `POST /ai-reference-answers` — triggers generation for
 * one `ExtractedQuestion`. Without `force`, a question that already has a
 * `pending_verification`/`approved` current reference is a no-op
 * returning that row; `force` always creates a new version. */
export interface AIReferenceAnswerGenerate {
  extracted_question_id: string;
  force?: boolean;
}

export interface AIReferenceAnswerReject {
  reason: string;
}
