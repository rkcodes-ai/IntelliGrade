import { apiClient } from "@/api/client";
import type {
  AIReferenceAnswer,
  AIReferenceAnswerGenerate,
  AIReferenceAnswerReject,
} from "@/types/aiReferenceAnswer";
import type { Page, PageParams } from "@/types/pagination";

/**
 * `POST ""` triggers `ReferenceAnswerService.generate()` — not a raw
 * create, every content field is AI-computed server-side from the
 * official Model Answer. `approve`/`reject`/`regenerate` are the Teacher
 * Verification actions (Phase 7). See
 * `backend/app/api/v1/endpoints/ai_reference_answers.py`.
 */
export async function listAIReferenceAnswers(
  params?: PageParams,
): Promise<Page<AIReferenceAnswer>> {
  const { data } = await apiClient.get<Page<AIReferenceAnswer>>("/ai-reference-answers", {
    params,
  });
  return data;
}

export async function getAIReferenceAnswer(id: string): Promise<AIReferenceAnswer> {
  const { data } = await apiClient.get<AIReferenceAnswer>(`/ai-reference-answers/${id}`);
  return data;
}

export async function getCurrentAIReferenceAnswerForQuestion(
  extractedQuestionId: string,
): Promise<AIReferenceAnswer | null> {
  const { data } = await apiClient.get<AIReferenceAnswer | null>(
    `/ai-reference-answers/by-question/${extractedQuestionId}/current`,
  );
  return data;
}

export async function listAIReferenceAnswerVersions(
  extractedQuestionId: string,
): Promise<AIReferenceAnswer[]> {
  const { data } = await apiClient.get<AIReferenceAnswer[]>(
    `/ai-reference-answers/by-question/${extractedQuestionId}/versions`,
  );
  return data;
}

export async function generateAIReferenceAnswer(
  payload: AIReferenceAnswerGenerate,
): Promise<AIReferenceAnswer> {
  const { data } = await apiClient.post<AIReferenceAnswer>("/ai-reference-answers", payload);
  return data;
}

export async function approveAIReferenceAnswer(id: string): Promise<AIReferenceAnswer> {
  const { data } = await apiClient.post<AIReferenceAnswer>(`/ai-reference-answers/${id}/approve`);
  return data;
}

export async function rejectAIReferenceAnswer(
  id: string,
  payload: AIReferenceAnswerReject,
): Promise<AIReferenceAnswer> {
  const { data } = await apiClient.post<AIReferenceAnswer>(
    `/ai-reference-answers/${id}/reject`,
    payload,
  );
  return data;
}

/** Always creates a new version — see `ReferenceAnswerService.regenerate()`. */
export async function regenerateAIReferenceAnswer(
  extractedQuestionId: string,
): Promise<AIReferenceAnswer> {
  const { data } = await apiClient.post<AIReferenceAnswer>(
    `/ai-reference-answers/by-question/${extractedQuestionId}/regenerate`,
  );
  return data;
}
