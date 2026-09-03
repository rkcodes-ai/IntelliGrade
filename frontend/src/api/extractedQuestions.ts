import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { ExtractedQuestion, ExtractedQuestionUpdate } from "@/types/officialExam";

/**
 * No `POST ""`/`DELETE` — rows are written internally by
 * `app.tasks.official_document_tasks` during ingestion; teacher
 * verification only edits/confirms an already-extracted row (see
 * `backend/app/api/v1/endpoints/extracted_questions.py`).
 */
export async function listExtractedQuestions(
  params?: PageParams & { document_id?: string },
): Promise<Page<ExtractedQuestion>> {
  const { data } = await apiClient.get<Page<ExtractedQuestion>>("/extracted-questions", { params });
  return data;
}

export async function getExtractedQuestion(id: string): Promise<ExtractedQuestion> {
  const { data } = await apiClient.get<ExtractedQuestion>(`/extracted-questions/${id}`);
  return data;
}

export async function updateExtractedQuestion(
  id: string,
  payload: ExtractedQuestionUpdate,
): Promise<ExtractedQuestion> {
  const { data } = await apiClient.patch<ExtractedQuestion>(`/extracted-questions/${id}`, payload);
  return data;
}

export async function verifyExtractedQuestion(id: string): Promise<ExtractedQuestion> {
  const { data } = await apiClient.post<ExtractedQuestion>(`/extracted-questions/${id}/verify`);
  return data;
}
