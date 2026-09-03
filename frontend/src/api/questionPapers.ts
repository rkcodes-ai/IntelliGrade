import { apiClient } from "@/api/client";
import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionPaper,
  QuestionPaperCreate,
  QuestionPaperRejectRequest,
  QuestionPaperUpdate,
  QuestionPaperVersion,
  QuestionPaperVersionSnapshotRequest,
} from "@/types/assessment";

export const questionPapersApi = createCrudApi<
  QuestionPaper,
  QuestionPaperCreate,
  QuestionPaperUpdate
>("/question-papers");

export async function submitQuestionPaperForReview(id: string): Promise<QuestionPaper> {
  const { data } = await apiClient.post<QuestionPaper>(`/question-papers/${id}/submit-for-review`);
  return data;
}

export async function approveQuestionPaper(id: string): Promise<QuestionPaper> {
  const { data } = await apiClient.post<QuestionPaper>(`/question-papers/${id}/approve`);
  return data;
}

export async function rejectQuestionPaper(
  id: string,
  payload: QuestionPaperRejectRequest,
): Promise<QuestionPaper> {
  const { data } = await apiClient.post<QuestionPaper>(`/question-papers/${id}/reject`, payload);
  return data;
}

/** Snapshots this question paper's current state into a new, immutable `QuestionPaperVersion` row. */
export async function createQuestionPaperVersionSnapshot(
  id: string,
  payload: QuestionPaperVersionSnapshotRequest,
): Promise<QuestionPaperVersion> {
  const { data } = await apiClient.post<QuestionPaperVersion>(
    `/question-papers/${id}/versions`,
    payload,
  );
  return data;
}
