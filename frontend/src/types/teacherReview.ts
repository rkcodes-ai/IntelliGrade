/**
 * Types mirroring the backend's Teacher Review, Result Finalization &
 * Analytics (Module 07) Pydantic schemas (`backend/app/schemas/*.py`)
 * field-for-field, including snake_case casing — same convention as
 * `types/officialExam.ts`. `Decimal`/`Numeric` backend fields are
 * `string` on Read shapes.
 */

/* ---------------------------------------------------------------------------
 * Teacher Review Dashboard (Feature 1)
 * ------------------------------------------------------------------------ */

export interface TeacherReviewFilters {
  exam_id?: string | null;
  subject_id?: string | null;
  course_id?: string | null;
  department_id?: string | null;
  student_user_id?: string | null;
  confidence_tier?: string | null;
  review_status?: string | null;
  teacher_id?: string | null;
}

export interface TeacherReviewDashboardSummary {
  pending_review_count: number;
  medium_confidence_count: number;
  low_confidence_count: number;
  completed_reviews_count: number;
  auto_accepted_count: number;
}

/* ---------------------------------------------------------------------------
 * Exam Result — Finalization & Locking (Features 4/5, ADR-042)
 * ------------------------------------------------------------------------ */

export type ExamResultStatus = "draft" | "under_review" | "approved" | "locked" | "published";

export interface ExamResult {
  id: string;
  institution_id: string;
  exam_session_id: string;
  status: ExamResultStatus;
  total_max_marks: string | null;
  total_marks: string | null;
  finalized_by: string | null;
  finalized_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  locked_by: string | null;
  locked_at: string | null;
  published_by: string | null;
  published_at: string | null;
  unlocked_by: string | null;
  unlocked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FinalizeStudentRequest {
  exam_session_id: string;
}

export interface FinalizeExamRequest {
  exam_id: string;
}

export interface FinalizeBatchRequest {
  exam_id: string;
  batch_id: string;
}

export interface BulkExamRequest {
  exam_id: string;
}

export interface BulkActionFailure {
  reference_id: string;
  reason: string;
}

export interface BulkActionResult {
  succeeded_count: number;
  failed: BulkActionFailure[];
}

/* ---------------------------------------------------------------------------
 * Analytics Dashboard (Feature 7, ADR-044)
 * ------------------------------------------------------------------------ */

export interface AnalyticsFilters {
  exam_id?: string | null;
  subject_id?: string | null;
  course_id?: string | null;
  department_id?: string | null;
}

export interface ConfidenceDistribution {
  high: number;
  medium: number;
  low: number;
}

export interface AnalyticsOverview {
  result_count: number;
  average_marks: string | null;
  highest_marks: string | null;
  lowest_marks: string | null;
  pass_percentage: string | null;
  fail_percentage: string | null;
  confidence_distribution: ConfidenceDistribution;
  teacher_override_percentage: string | null;
  average_ai_vs_teacher_difference: string | null;
}

export interface QuestionPerformance {
  extracted_question_id: string;
  question_number: string;
  evaluated_count: number;
  max_marks: string;
  average_marks: string | null;
  average_ratio: string | null;
}

export interface QuestionWiseAnalytics {
  questions: QuestionPerformance[];
  most_difficult: QuestionPerformance[];
}

/* ---------------------------------------------------------------------------
 * Reports (Feature 8, ADR-045)
 * ------------------------------------------------------------------------ */

export type ReportType =
  | "student"
  | "question_wise"
  | "teacher_review"
  | "ai_performance"
  | "institution_summary"
  | "department_summary"
  | "course_summary";

export type ReportFormat = "pdf" | "excel" | "csv";
export type ReportJobStatus = "pending" | "processing" | "completed" | "failed";

export interface ReportGenerateRequest {
  report_type: ReportType;
  format: ReportFormat;
  parameters?: Record<string, unknown> | null;
}

export interface ReportJob {
  id: string;
  institution_id: string;
  report_type: ReportType;
  format: ReportFormat;
  parameters: Record<string, unknown> | null;
  requested_by: string;
  status: ReportJobStatus;
  storage_key: string | null;
  failure_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------------------------------------------------------------------------
 * Global Search (Feature 9)
 * ------------------------------------------------------------------------ */

export type SearchResultType = "student" | "teacher" | "subject" | "question" | "evaluation";

export interface SearchResultItem {
  type: SearchResultType;
  id: string;
  label: string;
  subtitle: string | null;
}

export interface SearchResults {
  query: string;
  results: SearchResultItem[];
}

/* ---------------------------------------------------------------------------
 * Notifications (Feature 10, ADR-046)
 * ------------------------------------------------------------------------ */

export interface NotificationEvent {
  id: string;
  institution_id: string;
  recipient_user_id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
  updated_at: string;
}
