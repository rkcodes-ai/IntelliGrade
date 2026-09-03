import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { ExtractedModelAnswer, ExtractedModelAnswerUpdate } from "@/types/officialExam";

/**
 * No `POST ""`/`DELETE` — rows are written internally by
 * `app.tasks.official_document_tasks` during ingestion; teacher
 * verification only edits/confirms an already-extracted row (see
 * `backend/app/api/v1/endpoints/extracted_model_answers.py`).
 */
export async function listExtractedModelAnswers(
  params?: PageParams & { document_id?: string },
): Promise<Page<ExtractedModelAnswer>> {
  const { data } = await apiClient.get<Page<ExtractedModelAnswer>>("/extracted-model-answers", {
    params,
  });
  return data;
}

export async function getExtractedModelAnswer(id: string): Promise<ExtractedModelAnswer> {
  const { data } = await apiClient.get<ExtractedModelAnswer>(`/extracted-model-answers/${id}`);
  return data;
}

export async function updateExtractedModelAnswer(
  id: string,
  payload: ExtractedModelAnswerUpdate,
): Promise<ExtractedModelAnswer> {
  const { data } = await apiClient.patch<ExtractedModelAnswer>(
    `/extracted-model-answers/${id}`,
    payload,
  );
  return data;
}

export async function verifyExtractedModelAnswer(id: string): Promise<ExtractedModelAnswer> {
  const { data } = await apiClient.post<ExtractedModelAnswer>(
    `/extracted-model-answers/${id}/verify`,
  );
  return data;
}
