import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type {
  BulkActionResult,
  BulkExamRequest,
  ExamResult,
  FinalizeBatchRequest,
  FinalizeExamRequest,
  FinalizeStudentRequest,
} from "@/types/teacherReview";

/**
 * Result Finalization & Locking (Module 07, ADR-042). `finalize*` cover
 * Feature 4's three finalization granularities; `approve/lock/unlock/
 * publish` are Feature 5's validated state-machine transitions; the
 * `bulk*` actions cover Feature 11's bulk approval/lock/publish. See
 * `backend/app/api/v1/endpoints/exam_results.py`.
 */
export async function listExamResults(params?: PageParams): Promise<Page<ExamResult>> {
  const { data } = await apiClient.get<Page<ExamResult>>("/exam-results", { params });
  return data;
}

export async function getExamResult(id: string): Promise<ExamResult> {
  const { data } = await apiClient.get<ExamResult>(`/exam-results/${id}`);
  return data;
}

export async function finalizeStudentResult(payload: FinalizeStudentRequest): Promise<ExamResult> {
  const { data } = await apiClient.post<ExamResult>("/exam-results/finalize-student", payload);
  return data;
}

export async function finalizeExamResults(
  payload: FinalizeExamRequest,
): Promise<BulkActionResult> {
  const { data } = await apiClient.post<BulkActionResult>("/exam-results/finalize-exam", payload);
  return data;
}

export async function finalizeBatchResults(
  payload: FinalizeBatchRequest,
): Promise<BulkActionResult> {
  const { data } = await apiClient.post<BulkActionResult>("/exam-results/finalize-batch", payload);
  return data;
}

export async function approveExamResult(id: string): Promise<ExamResult> {
  const { data } = await apiClient.post<ExamResult>(`/exam-results/${id}/approve`);
  return data;
}

export async function lockExamResult(id: string): Promise<ExamResult> {
  const { data } = await apiClient.post<ExamResult>(`/exam-results/${id}/lock`);
  return data;
}

export async function unlockExamResult(id: string): Promise<ExamResult> {
  const { data } = await apiClient.post<ExamResult>(`/exam-results/${id}/unlock`);
  return data;
}

export async function publishExamResult(id: string): Promise<ExamResult> {
  const { data } = await apiClient.post<ExamResult>(`/exam-results/${id}/publish`);
  return data;
}

export async function bulkApproveExamResults(
  payload: BulkExamRequest,
): Promise<BulkActionResult> {
  const { data } = await apiClient.post<BulkActionResult>("/exam-results/bulk/approve", payload);
  return data;
}

export async function bulkLockExamResults(payload: BulkExamRequest): Promise<BulkActionResult> {
  const { data } = await apiClient.post<BulkActionResult>("/exam-results/bulk/lock", payload);
  return data;
}

export async function bulkPublishExamResults(
  payload: BulkExamRequest,
): Promise<BulkActionResult> {
  const { data } = await apiClient.post<BulkActionResult>("/exam-results/bulk/publish", payload);
  return data;
}
