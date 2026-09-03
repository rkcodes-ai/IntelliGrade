/**
 * Types mirroring the backend's Assessment Domain (Module 04) Pydantic
 * schemas (`backend/app/schemas/*.py`) field-for-field, including snake_case
 * casing — same convention as `types/academic.ts` (see its file-level
 * comment). `Decimal` backend fields are `string` on the Read shape (Pydantic
 * serializes `Decimal` as a JSON string) and `number` on Create/Update
 * payloads, exactly like `types/academic.ts`'s `Subject.credits`.
 */

/* ---------------------------------------------------------------------------
 * Assessment Core
 * ------------------------------------------------------------------------ */

export interface AssessmentType {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssessmentTypeCreate {
  code: string;
  name: string;
  description?: string | null;
}

export type AssessmentTypeUpdate = Partial<AssessmentTypeCreate> & { is_active?: boolean };

export interface AssessmentStatus {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  description: string | null;
  is_terminal: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssessmentStatusCreate {
  code: string;
  name: string;
  description?: string | null;
  is_terminal?: boolean;
}

export type AssessmentStatusUpdate = Partial<AssessmentStatusCreate> & { is_active?: boolean };

export interface Assessment {
  id: string;
  institution_id: string;
  subject_id: string;
  assessment_type_id: string;
  assessment_status_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface AssessmentCreate {
  subject_id: string;
  assessment_type_id: string;
  assessment_status_id: string;
  name: string;
  description?: string | null;
}

export type AssessmentUpdate = Partial<AssessmentCreate> & { is_active?: boolean };

export interface AssessmentConfiguration {
  id: string;
  institution_id: string;
  assessment_id: string;
  maximum_marks: string;
  passing_marks: string;
  negative_marks: string | null;
  grace_marks: string | null;
  time_limit_minutes: number | null;
  attempt_rules: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssessmentConfigurationCreate {
  assessment_id: string;
  maximum_marks: number;
  passing_marks: number;
  negative_marks?: number | null;
  grace_marks?: number | null;
  time_limit_minutes?: number | null;
  attempt_rules?: Record<string, unknown> | null;
}

/**
 * Deliberately excludes `assessment_id` — the parent link is fixed at
 * creation (see `backend/app/schemas/assessment_configuration.py`), so this
 * is NOT `Partial<AssessmentConfigurationCreate>`.
 */
export interface AssessmentConfigurationUpdate {
  maximum_marks?: number;
  passing_marks?: number;
  negative_marks?: number | null;
  grace_marks?: number | null;
  time_limit_minutes?: number | null;
  attempt_rules?: Record<string, unknown> | null;
  is_active?: boolean;
}

export type EvaluationMode = "manual" | "auto" | "hybrid";

export interface EvaluationConfiguration {
  id: string;
  institution_id: string;
  assessment_id: string;
  evaluation_mode: string;
  confidence_threshold: string | null;
  ai_config: Record<string, unknown> | null;
  auto_publish_results: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EvaluationConfigurationCreate {
  assessment_id: string;
  evaluation_mode: EvaluationMode;
  confidence_threshold?: number | null;
  ai_config?: Record<string, unknown> | null;
  auto_publish_results?: boolean;
}

/** Deliberately excludes `assessment_id` — the parent link is fixed at creation. */
export interface EvaluationConfigurationUpdate {
  evaluation_mode?: EvaluationMode;
  confidence_threshold?: number | null;
  ai_config?: Record<string, unknown> | null;
  auto_publish_results?: boolean;
  is_active?: boolean;
}

export interface Exam {
  id: string;
  institution_id: string;
  assessment_id: string;
  section_id: string;
  name: string;
  exam_date: string;
  is_active: boolean;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface ExamCreate {
  assessment_id: string;
  section_id: string;
  name: string;
  exam_date: string;
}

export type ExamUpdate = Partial<ExamCreate> & { is_active?: boolean };

export interface ExamInstructions {
  id: string;
  institution_id: string;
  exam_id: string;
  instructions_text: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExamInstructionsCreate {
  exam_id: string;
  instructions_text: string;
  display_order?: number;
}

export type ExamInstructionsUpdate = Partial<ExamInstructionsCreate> & { is_active?: boolean };

export interface ExamSchedule {
  id: string;
  institution_id: string;
  exam_id: string;
  room_id: string | null;
  start_time: string;
  end_time: string;
  invigilator_user_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExamScheduleCreate {
  exam_id: string;
  room_id?: string | null;
  start_time: string;
  end_time: string;
  invigilator_user_id?: string | null;
}

export type ExamScheduleUpdate = Partial<ExamScheduleCreate> & { is_active?: boolean };

export type ExamSessionStatus = "not_started" | "in_progress" | "submitted" | "evaluated" | "absent";

export interface ExamSession {
  id: string;
  institution_id: string;
  exam_id: string;
  student_user_id: string;
  status: ExamSessionStatus;
  started_at: string | null;
  submitted_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExamSessionCreate {
  exam_id: string;
  student_user_id: string;
  status?: ExamSessionStatus;
  started_at?: string | null;
  submitted_at?: string | null;
}

export type ExamSessionUpdate = Partial<ExamSessionCreate> & { is_active?: boolean };

/* ---------------------------------------------------------------------------
 * Question Bank
 * ------------------------------------------------------------------------ */

export interface QuestionCategory {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuestionCategoryCreate {
  code: string;
  name: string;
  description?: string | null;
}

export type QuestionCategoryUpdate = Partial<QuestionCategoryCreate> & { is_active?: boolean };

export interface QuestionType {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  description: string | null;
  requires_options: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuestionTypeCreate {
  code: string;
  name: string;
  description?: string | null;
  requires_options?: boolean;
}

export type QuestionTypeUpdate = Partial<QuestionTypeCreate> & { is_active?: boolean };

export interface DifficultyLevel {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  level_order: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DifficultyLevelCreate {
  code: string;
  name: string;
  level_order: number;
  description?: string | null;
}

export type DifficultyLevelUpdate = Partial<DifficultyLevelCreate> & { is_active?: boolean };

export interface BloomTaxonomyLevel {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  level_order: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BloomTaxonomyLevelCreate {
  code: string;
  name: string;
  level_order: number;
  description?: string | null;
}

export type BloomTaxonomyLevelUpdate = Partial<BloomTaxonomyLevelCreate> & { is_active?: boolean };

export interface QuestionTag {
  id: string;
  institution_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuestionTagCreate {
  name: string;
  description?: string | null;
}

export type QuestionTagUpdate = Partial<QuestionTagCreate> & { is_active?: boolean };

/**
 * Mirrors `ApprovalWorkflowMixin`'s draft -> pending_review ->
 * approved/rejected -> archived lifecycle — shared by `Question` and
 * `QuestionPaper` (identical `Literal` redefined in both
 * `backend/app/schemas/question.py` and `backend/app/schemas/question_paper.py`).
 */
export type ApprovalStatus = "draft" | "pending_review" | "approved" | "rejected" | "archived";

export interface Question {
  id: string;
  institution_id: string;
  subject_id: string;
  question_category_id: string;
  question_type_id: string;
  difficulty_level_id: string;
  bloom_level_id: string;
  unit: string | null;
  chapter: string | null;
  topic: string | null;
  subtopic: string | null;
  learning_outcome: string | null;
  question_text: string;
  estimated_time_minutes: number | null;
  marks: string;
  language: string;
  attachments: unknown[] | null;
  diagram_url: string | null;
  question_metadata: Record<string, unknown> | null;
  is_active: boolean;
  current_version: number;
  approval_status: ApprovalStatus;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionCreate {
  subject_id: string;
  question_category_id: string;
  question_type_id: string;
  difficulty_level_id: string;
  bloom_level_id: string;
  unit?: string | null;
  chapter?: string | null;
  topic?: string | null;
  subtopic?: string | null;
  learning_outcome?: string | null;
  question_text: string;
  estimated_time_minutes?: number | null;
  marks: number;
  language?: string;
  attachments?: unknown[] | null;
  diagram_url?: string | null;
  question_metadata?: Record<string, unknown> | null;
}

/**
 * Deliberately excludes `approval_status`/`approved_by`/`approved_at`/
 * `rejection_reason` — those transition only through the dedicated
 * `/submit-for-review`, `/approve`, `/reject` endpoints, never via a generic
 * PATCH (see `backend/app/schemas/question.py`).
 */
export type QuestionUpdate = Partial<QuestionCreate> & { is_active?: boolean };

export interface QuestionRejectRequest {
  reason: string;
}

export interface QuestionTagAddRequest {
  tag_id: string;
}

export interface QuestionTagMapRead {
  id: string;
  institution_id: string;
  question_id: string;
  tag_id: string;
  created_at: string;
}

/**
 * Append-only snapshot history for `Question`. There is deliberately no
 * `QuestionVersionCreate`/`QuestionVersionUpdate` — rows are created only via
 * `POST /questions/{question_id}/versions` (see `questionsApi` in
 * `api/questions.ts`), never through a generic create.
 */
export interface QuestionVersion {
  id: string;
  institution_id: string;
  question_id: string;
  version_number: number;
  question_text: string;
  marks: string;
  difficulty_level_id: string;
  change_reason: string | null;
  changed_by: string | null;
  created_at: string;
  updated_at: string;
}

/** Body for `POST /questions/{question_id}/versions`. */
export interface QuestionVersionSnapshotRequest {
  change_reason?: string | null;
}

/** Mirrors `QuestionApproval.decision`'s plain-string column. */
export type ApprovalDecision = "approved" | "rejected";

/**
 * The formal approve/reject decision audit trail for `Question`. Read-only
 * from the frontend's perspective: `backend/app/api/v1/endpoints/question_approvals.py`
 * exposes only `GET ""`/`GET "/{id}"` — rows are inserted internally by
 * `QuestionApprovalService`, not via a client-facing `POST`.
 */
export interface QuestionApproval {
  id: string;
  institution_id: string;
  question_id: string;
  question_version_id: string | null;
  decision: ApprovalDecision;
  reviewed_by: string | null;
  reviewed_at: string;
  comments: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Mirrors `QuestionApprovalCreate` field-for-field. No HTTP endpoint accepts
 * this payload today (see `QuestionApproval` doc comment above) — kept here
 * only for schema parity in case a route is wired up later.
 */
export interface QuestionApprovalCreate {
  question_id: string;
  question_version_id?: string | null;
  decision: ApprovalDecision;
  comments?: string | null;
}

export interface QuestionReview {
  id: string;
  institution_id: string;
  question_id: string;
  reviewer_id: string | null;
  comment: string;
  rating: number | null;
  created_at: string;
  updated_at: string;
}

/** `reviewer_id` is deliberately absent: the router sets it from the current user. */
export interface QuestionReviewCreate {
  question_id: string;
  comment: string;
  rating?: number | null;
}

/**
 * Deliberately excludes `question_id` — unlike most Update shapes in this
 * module, so this is NOT `Partial<QuestionReviewCreate>`.
 */
export interface QuestionReviewUpdate {
  comment?: string;
  rating?: number | null;
}

/* ---------------------------------------------------------------------------
 * Question Paper
 * ------------------------------------------------------------------------ */

export interface QuestionBlueprint {
  id: string;
  institution_id: string;
  subject_id: string;
  name: string;
  total_marks: string;
  total_questions: number;
  is_active: boolean;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface QuestionBlueprintCreate {
  subject_id: string;
  name: string;
  total_marks: number;
  total_questions: number;
}

export type QuestionBlueprintUpdate = Partial<QuestionBlueprintCreate> & { is_active?: boolean };

export interface QuestionBlueprintSection {
  id: string;
  institution_id: string;
  blueprint_id: string;
  question_category_id: string | null;
  difficulty_level_id: string | null;
  bloom_level_id: string | null;
  question_type_id: string | null;
  number_of_questions: number;
  marks_per_question: string;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface QuestionBlueprintSectionCreate {
  blueprint_id: string;
  question_category_id?: string | null;
  difficulty_level_id?: string | null;
  bloom_level_id?: string | null;
  question_type_id?: string | null;
  number_of_questions: number;
  marks_per_question: number;
  display_order?: number;
}

export type QuestionBlueprintSectionUpdate = Partial<QuestionBlueprintSectionCreate>;

export interface QuestionPaperTemplate {
  id: string;
  institution_id: string;
  name: string;
  description: string | null;
  header_text: string | null;
  footer_text: string | null;
  instructions_text: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuestionPaperTemplateCreate {
  name: string;
  description?: string | null;
  header_text?: string | null;
  footer_text?: string | null;
  instructions_text?: string | null;
}

export type QuestionPaperTemplateUpdate = Partial<QuestionPaperTemplateCreate> & {
  is_active?: boolean;
};

export interface QuestionPaper {
  id: string;
  institution_id: string;
  assessment_id: string;
  blueprint_id: string | null;
  template_id: string | null;
  name: string;
  total_marks: string;
  is_active: boolean;
  current_version: number;
  approval_status: ApprovalStatus;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionPaperCreate {
  assessment_id: string;
  blueprint_id?: string | null;
  template_id?: string | null;
  name: string;
  total_marks: number;
}

/**
 * Deliberately excludes `approval_status`/`approved_by`/`approved_at`/
 * `rejection_reason` — those transition only through the dedicated
 * `/submit-for-review`, `/approve`, `/reject` endpoints, never via a generic
 * PATCH (see `backend/app/schemas/question_paper.py`).
 */
export type QuestionPaperUpdate = Partial<QuestionPaperCreate> & { is_active?: boolean };

export interface QuestionPaperRejectRequest {
  reason: string;
}

/**
 * Append-only snapshot history for `QuestionPaper`. Read-only from the
 * frontend's perspective — rows are created only via
 * `POST /question-papers/{id}/versions` (see `questionPapersApi` in
 * `api/questionPapers.ts`); `backend/app/api/v1/endpoints/question_paper_versions.py`
 * exposes only `GET ""`/`GET "/{id}"`.
 */
export interface QuestionPaperVersion {
  id: string;
  institution_id: string;
  question_paper_id: string;
  version_number: number;
  snapshot: Record<string, unknown>;
  change_reason: string | null;
  changed_by: string | null;
  created_at: string;
  updated_at: string;
}

/** Body of `POST /question-papers/{id}/versions`. */
export interface QuestionPaperVersionSnapshotRequest {
  change_reason?: string | null;
}

export interface QuestionPaperSection {
  id: string;
  institution_id: string;
  question_paper_id: string;
  name: string;
  instructions: string | null;
  marks_per_question: string | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuestionPaperSectionCreate {
  question_paper_id: string;
  name: string;
  instructions?: string | null;
  marks_per_question?: number | null;
  display_order?: number;
}

export type QuestionPaperSectionUpdate = Partial<QuestionPaperSectionCreate> & {
  is_active?: boolean;
};

export interface QuestionPaperQuestionMapping {
  id: string;
  institution_id: string;
  question_paper_section_id: string;
  question_id: string;
  order_index: number;
  marks_override: string | null;
  is_optional: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuestionPaperQuestionMappingCreate {
  question_paper_section_id: string;
  question_id: string;
  order_index?: number;
  marks_override?: number | null;
  is_optional?: boolean;
}

export type QuestionPaperQuestionMappingUpdate = Partial<QuestionPaperQuestionMappingCreate>;

export type StrategyType = "none" | "shuffle_questions" | "shuffle_options" | "pick_random_subset";

export interface RandomizationStrategy {
  id: string;
  institution_id: string;
  question_paper_id: string | null;
  question_paper_section_id: string | null;
  strategy_type: StrategyType;
  config: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RandomizationStrategyCreate {
  question_paper_id?: string | null;
  question_paper_section_id?: string | null;
  strategy_type?: StrategyType;
  config?: Record<string, unknown> | null;
}

export type RandomizationStrategyUpdate = Partial<RandomizationStrategyCreate> & {
  is_active?: boolean;
};

/* ---------------------------------------------------------------------------
 * Answer Key / Rubric
 * ------------------------------------------------------------------------ */

export interface AnswerKey {
  id: string;
  institution_id: string;
  question_id: string;
  reference_answer: string;
  expected_length: number | null;
  expected_structure: Record<string, unknown> | null;
  confidence_threshold: string | null;
  ai_config: Record<string, unknown> | null;
  evaluation_notes: string | null;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface AnswerKeyCreate {
  question_id: string;
  reference_answer: string;
  expected_length?: number | null;
  expected_structure?: Record<string, unknown> | null;
  /** AI-preparation placeholder per ADR-024 — not used by any code yet. */
  confidence_threshold?: number | null;
  /** AI-preparation placeholder per ADR-024 — not used by any code yet. */
  ai_config?: Record<string, unknown> | null;
  evaluation_notes?: string | null;
}

/**
 * Deliberately excludes `question_id` — the 1:1 link to its `Question` is
 * fixed at creation, so this is NOT `Partial<AnswerKeyCreate>`.
 */
export interface AnswerKeyUpdate {
  reference_answer?: string;
  expected_length?: number | null;
  expected_structure?: Record<string, unknown> | null;
  confidence_threshold?: number | null;
  ai_config?: Record<string, unknown> | null;
  evaluation_notes?: string | null;
}

export interface ModelAnswer {
  id: string;
  institution_id: string;
  answer_key_id: string;
  content: string;
  marks_allocated: string | null;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface ModelAnswerCreate {
  answer_key_id: string;
  content: string;
  marks_allocated?: number | null;
  display_order?: number;
}

/** Deliberately excludes `answer_key_id` — the parent link is fixed at creation. */
export interface ModelAnswerUpdate {
  content?: string;
  marks_allocated?: number | null;
  display_order?: number;
}

export interface AlternativeAnswer {
  id: string;
  institution_id: string;
  answer_key_id: string;
  content: string;
  is_exact_match: boolean;
  created_at: string;
  updated_at: string;
}

export interface AlternativeAnswerCreate {
  answer_key_id: string;
  content: string;
  is_exact_match?: boolean;
}

/** Deliberately excludes `answer_key_id` — the parent link is fixed at creation. */
export interface AlternativeAnswerUpdate {
  content?: string;
  is_exact_match?: boolean;
}

/**
 * `"ai_note"` is a category placeholder per ADR-024 for future AI-generated
 * notes — no code writes one yet.
 */
export type NoteType = "teacher_note" | "ai_note";

export interface ReferenceNote {
  id: string;
  institution_id: string;
  answer_key_id: string;
  note_text: string;
  note_type: NoteType;
  created_at: string;
  updated_at: string;
}

export interface ReferenceNoteCreate {
  answer_key_id: string;
  note_text: string;
  note_type?: NoteType;
}

/** Deliberately excludes `answer_key_id` — the parent link is fixed at creation. */
export interface ReferenceNoteUpdate {
  note_text?: string;
  note_type?: NoteType;
}

export interface Rubric {
  id: string;
  institution_id: string;
  question_id: string | null;
  name: string;
  total_marks: string;
  is_active: boolean;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface RubricCreate {
  question_id?: string | null;
  name: string;
  total_marks: number;
}

export type RubricUpdate = Partial<RubricCreate> & { is_active?: boolean };

export interface RubricCriterion {
  id: string;
  institution_id: string;
  rubric_id: string;
  parent_criterion_id: string | null;
  name: string;
  weightage_percent: string | null;
  max_marks: string;
  is_mandatory: boolean;
  teacher_notes: string | null;
  ai_notes: string | null;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface RubricCriterionCreate {
  rubric_id: string;
  parent_criterion_id?: string | null;
  name: string;
  weightage_percent?: number | null;
  max_marks: number;
  is_mandatory?: boolean;
  teacher_notes?: string | null;
  ai_notes?: string | null;
  display_order?: number;
}

/**
 * Deliberately excludes `rubric_id` — the parent link is fixed at creation,
 * so this is NOT `Partial<RubricCriterionCreate>`.
 */
export interface RubricCriterionUpdate {
  parent_criterion_id?: string | null;
  name?: string;
  weightage_percent?: number | null;
  max_marks?: number;
  is_mandatory?: boolean;
  teacher_notes?: string | null;
  ai_notes?: string | null;
  display_order?: number;
}

export interface MarkDistribution {
  id: string;
  institution_id: string;
  rubric_criterion_id: string;
  band_name: string;
  min_score: string;
  max_score: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarkDistributionCreate {
  rubric_criterion_id: string;
  band_name: string;
  min_score: number;
  max_score: number;
  description?: string | null;
}

/** Deliberately excludes `rubric_criterion_id` — the parent link is fixed at creation. */
export interface MarkDistributionUpdate {
  band_name?: string;
  min_score?: number;
  max_score?: number;
  description?: string | null;
}

export interface ExpectedKeyword {
  id: string;
  institution_id: string;
  answer_key_id: string | null;
  rubric_criterion_id: string | null;
  keyword: string;
  weight: string | null;
  is_mandatory: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExpectedKeywordCreate {
  answer_key_id?: string | null;
  rubric_criterion_id?: string | null;
  keyword: string;
  weight?: number | null;
  is_mandatory?: boolean;
}

export type ExpectedKeywordUpdate = Partial<ExpectedKeywordCreate>;

export interface ExpectedConcept {
  id: string;
  institution_id: string;
  answer_key_id: string | null;
  rubric_criterion_id: string | null;
  concept_name: string;
  description: string | null;
  is_mandatory: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExpectedConceptCreate {
  answer_key_id?: string | null;
  rubric_criterion_id?: string | null;
  concept_name: string;
  description?: string | null;
  is_mandatory?: boolean;
}

export type ExpectedConceptUpdate = Partial<ExpectedConceptCreate>;

/* ---------------------------------------------------------------------------
 * AI-prep
 * ------------------------------------------------------------------------ */

export type EvaluatorType = "human" | "ai";

/**
 * Append-only in practice — there is deliberately no `EvaluationHistoryUpdate`
 * schema, since no permission code or route exists to use one (see
 * `backend/app/schemas/evaluation_history.py`).
 */
export interface EvaluationHistory {
  id: string;
  institution_id: string;
  exam_session_id: string;
  answer_key_id: string | null;
  evaluator_type: EvaluatorType;
  evaluator_user_id: string | null;
  score: string | null;
  confidence_score: string | null;
  embedding_vector: unknown[] | null;
  evaluated_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationHistoryCreate {
  exam_session_id: string;
  answer_key_id?: string | null;
  evaluator_type?: EvaluatorType;
  evaluator_user_id?: string | null;
  score?: number | null;
  confidence_score?: number | null;
  embedding_vector?: unknown[] | null;
  evaluated_at?: string | null;
  notes?: string | null;
}
