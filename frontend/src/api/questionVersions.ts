import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { QuestionVersion } from "@/types/assessment";

/**
 * Append-only snapshot history for `Question` — creation happens exclusively
 * via `createQuestionVersionSnapshot` in `api/questions.ts`
 * (`POST /questions/{question_id}/versions`), so this is NOT a
 * `createCrudApi` object: `backend/app/api/v1/endpoints/question_versions.py`
 * has no `POST ""` or `PATCH "/{id}"` route.
 */
export async function listQuestionVersions(params?: PageParams): Promise<Page<QuestionVersion>> {
  const { data } = await apiClient.get<Page<QuestionVersion>>("/question-versions", { params });
  return data;
}

export async function listDeletedQuestionVersions(
  params?: PageParams,
): Promise<Page<QuestionVersion>> {
  const { data } = await apiClient.get<Page<QuestionVersion>>("/question-versions/deleted", {
    params,
  });
  return data;
}

export async function getQuestionVersion(id: string): Promise<QuestionVersion> {
  const { data } = await apiClient.get<QuestionVersion>(`/question-versions/${id}`);
  return data;
}

export async function removeQuestionVersion(id: string): Promise<void> {
  await apiClient.delete(`/question-versions/${id}`);
}

export async function restoreQuestionVersion(id: string): Promise<QuestionVersion> {
  const { data } = await apiClient.post<QuestionVersion>(`/question-versions/${id}/restore`);
  return data;
}
