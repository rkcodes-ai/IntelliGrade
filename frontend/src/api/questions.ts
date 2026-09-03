import { apiClient } from "@/api/client";
import { createCrudApi } from "@/api/createCrudApi";
import type {
  Question,
  QuestionCreate,
  QuestionRejectRequest,
  QuestionTagAddRequest,
  QuestionTagMapRead,
  QuestionUpdate,
  QuestionVersion,
  QuestionVersionSnapshotRequest,
} from "@/types/assessment";

export const questionsApi = createCrudApi<Question, QuestionCreate, QuestionUpdate>("/questions");

export async function submitQuestionForReview(id: string): Promise<Question> {
  const { data } = await apiClient.post<Question>(`/questions/${id}/submit-for-review`);
  return data;
}

export async function approveQuestion(id: string): Promise<Question> {
  const { data } = await apiClient.post<Question>(`/questions/${id}/approve`);
  return data;
}

export async function rejectQuestion(id: string, payload: QuestionRejectRequest): Promise<Question> {
  const { data } = await apiClient.post<Question>(`/questions/${id}/reject`, payload);
  return data;
}

export async function addQuestionTag(
  id: string,
  payload: QuestionTagAddRequest,
): Promise<QuestionTagMapRead> {
  const { data } = await apiClient.post<QuestionTagMapRead>(`/questions/${id}/tags`, payload);
  return data;
}

export async function removeQuestionTag(id: string, tagId: string): Promise<void> {
  await apiClient.delete(`/questions/${id}/tags/${tagId}`);
}

/** Snapshots this question's current state into a new, immutable `QuestionVersion` row. */
export async function createQuestionVersionSnapshot(
  questionId: string,
  payload: QuestionVersionSnapshotRequest,
): Promise<QuestionVersion> {
  const { data } = await apiClient.post<QuestionVersion>(
    `/questions/${questionId}/versions`,
    payload,
  );
  return data;
}
