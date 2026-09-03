/**
 * Types mirroring the backend's Answer Script OCR Pipeline (Module 05)
 * Pydantic schemas (`backend/app/schemas/*.py`) field-for-field, including
 * snake_case casing — same convention as `types/assessment.ts` (see its
 * file-level comment). `Decimal`/`Numeric` backend fields are `string` on
 * the Read shape and `number` on Create/Update payloads.
 */

/* ---------------------------------------------------------------------------
 * Answer Script / Upload
 * ------------------------------------------------------------------------ */

export type AnswerScriptStatus =
  | "uploading"
  | "uploaded"
  | "validating"
  | "validated"
  | "failed_validation"
  | "storing"
  | "stored"
  | "preprocessing"
  | "ocr_queued"
  | "ocr_running"
  | "ocr_complete"
  | "ocr_failed"
  | "structuring"
  | "completed"
  | "failed"
  | "cancelled";

export interface AnswerScript {
  id: string;
  institution_id: string;
  exam_session_id: string;
  uploaded_by: string;
  original_filename: string;
  mime_type: string;
  page_count: number | null;
  file_size_bytes: number;
  checksum_sha256: string | null;
  storage_key: string | null;
  status: AnswerScriptStatus;
  failure_reason: string | null;
  structured_content: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** `is_active` is the only client-patchable field — content/status fields are pipeline-managed. */
export interface AnswerScriptUpdate {
  is_active?: boolean;
}

export type AnswerScriptPageStatus =
  | "pending"
  | "preprocessing"
  | "preprocessed"
  | "ocr_running"
  | "ocr_complete"
  | "ocr_failed";

export interface AnswerScriptPage {
  id: string;
  institution_id: string;
  answer_script_id: string;
  page_number: number;
  storage_key: string | null;
  preprocessed_storage_key: string | null;
  width_px: number | null;
  height_px: number | null;
  is_blank: boolean;
  status: AnswerScriptPageStatus;
  /** Document Intelligence milestone — PageQualityAnalyzer/AdaptiveImageEnhancer
   * output; `null` for pages processed before this milestone or when quality
   * analysis/enhancement failed and safely fell back to the original image. */
  quality_score: string | null;
  quality_classification: string | null;
  quality_metrics: Record<string, unknown> | null;
  enhancement_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export type UploadJobStatus = "pending" | "in_progress" | "completed" | "failed" | "cancelled";

export interface UploadJob {
  id: string;
  institution_id: string;
  answer_script_id: string;
  upload_session_token: string;
  total_chunks: number | null;
  chunks_received: number;
  bytes_received: number;
  total_bytes: number | null;
  status: UploadJobStatus;
  retry_count: number;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------------------------------------------------------------------------
 * OCR Provider / Configuration / Job
 * ------------------------------------------------------------------------ */

export interface OCRProvider {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  is_implemented: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

/** `code`/`name`/`is_implemented` are immutable after seeding — only these two are patchable. */
export interface OCRProviderUpdate {
  is_enabled?: boolean;
  is_default?: boolean;
}

/** Live, on-demand engine health (Module 12) — never persisted, always a fresh check. */
export interface OCRProviderHealth {
  provider_code: string;
  installed: boolean;
  version: string | null;
  configured: boolean;
  authenticated: boolean | null;
  connectivity: boolean | null;
  dependencies_ok: boolean;
  gpu_available: boolean | null;
  ready: boolean;
  detail: string | null;
}

/** One provider's result within a `POST /ocr-providers/benchmark` report. */
export interface ProviderBenchmarkResult {
  provider_code: string;
  success: boolean;
  error: string | null;
  provider_version: string | null;
  processing_time_seconds: number | null;
  average_confidence: number | null;
  character_count: number;
  word_count: number;
  throughput_chars_per_second: number | null;
  cpu_percent: number | null;
  memory_delta_mb: number | null;
  gpu_available: boolean | null;
  word_accuracy: number | null;
  character_accuracy: number | null;
}

export interface BenchmarkReport {
  language: string;
  reference_text_supplied: boolean;
  results: ProviderBenchmarkResult[];
}

export interface OCRConfiguration {
  id: string;
  institution_id: string;
  assessment_id: string | null;
  ocr_provider_id: string;
  language: string;
  confidence_threshold: string | null;
  preprocessing_steps: string[] | null;
  max_retry_attempts: number;
  is_active: boolean;
  /** Ensemble Mode (Six-Provider OCR milestone) — opt-in, off by default. */
  is_ensemble_enabled: boolean;
  ensemble_provider_codes: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface OCRConfigurationCreate {
  assessment_id?: string | null;
  ocr_provider_id: string;
  language?: string;
  confidence_threshold?: number | null;
  preprocessing_steps?: string[] | null;
  max_retry_attempts?: number;
  is_ensemble_enabled?: boolean;
  ensemble_provider_codes?: string[] | null;
}

/** Deliberately excludes `assessment_id`/`ocr_provider_id` — fixed at creation. */
export interface OCRConfigurationUpdate {
  language?: string;
  confidence_threshold?: number | null;
  preprocessing_steps?: string[] | null;
  max_retry_attempts?: number;
  is_active?: boolean;
  is_ensemble_enabled?: boolean;
  ensemble_provider_codes?: string[] | null;
}

export type OCRJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface OCRJob {
  id: string;
  institution_id: string;
  answer_script_id: string;
  ocr_provider_id: string;
  /** Only non-null when a Phase 12 (Six-Provider OCR milestone) fallback
   * happened — the provider originally resolved before `ocr_provider_id`
   * (above) was swapped to the fallback target. */
  requested_ocr_provider_id: string | null;
  /** The original provider's real error message, when a fallback happened. */
  fallback_reason: string | null;
  celery_task_id: string | null;
  status: OCRJobStatus;
  priority: number;
  retry_count: number;
  max_retries: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface OCRJobCreate {
  answer_script_id: string;
  ocr_provider_id: string;
  priority?: number;
  max_retries?: number;
}

/* ---------------------------------------------------------------------------
 * OCR Result hierarchy (read-only)
 * ------------------------------------------------------------------------ */

export interface OCRResult {
  id: string;
  institution_id: string;
  answer_script_page_id: string;
  ocr_job_id: string;
  raw_text: string;
  normalized_text: string | null;
  average_confidence: string;
  language: string;
  rotation_degrees: string;
  reading_order_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface OCRBlock {
  id: string;
  institution_id: string;
  ocr_result_id: string;
  block_type: string;
  reading_order: number;
  bbox_left: number;
  bbox_top: number;
  bbox_width: number;
  bbox_height: number;
  confidence: string;
  created_at: string;
  updated_at: string;
}

export interface OCRLine {
  id: string;
  institution_id: string;
  ocr_block_id: string;
  text: string;
  reading_order: number;
  bbox_left: number;
  bbox_top: number;
  bbox_width: number;
  bbox_height: number;
  confidence: string;
  created_at: string;
  updated_at: string;
}

export interface OCRWord {
  id: string;
  institution_id: string;
  ocr_line_id: string;
  text: string;
  reading_order: number;
  bbox_left: number;
  bbox_top: number;
  bbox_width: number;
  bbox_height: number;
  confidence: string;
  created_at: string;
  updated_at: string;
}

export interface OCRLineWithChildren extends OCRLine {
  words: OCRWord[];
}

export interface OCRBlockWithChildren extends OCRBlock {
  lines: OCRLineWithChildren[];
}

/* ---------------------------------------------------------------------------
 * Processing History (read-only, append-only)
 * ------------------------------------------------------------------------ */

export type TriggeredBy = "system" | "user" | "retry";

export interface ProcessingHistory {
  id: string;
  institution_id: string;
  answer_script_id: string;
  stage: string;
  from_status: string | null;
  to_status: string;
  duration_ms: number | null;
  error_detail: string | null;
  triggered_by: TriggeredBy;
  created_at: string;
  updated_at: string;
}
