import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { AnswerScriptPage } from "@/types/ocr";

/**
 * Read-only: `backend/app/api/v1/endpoints/answer_script_pages.py` exposes
 * only `GET ""`/`GET "/{id}"` — pages are pipeline-managed, never
 * client-created.
 */
export async function listAnswerScriptPages(
  params?: PageParams & { answer_script_id?: string },
): Promise<Page<AnswerScriptPage>> {
  const { data } = await apiClient.get<Page<AnswerScriptPage>>("/answer-script-pages", { params });
  return data;
}

export async function getAnswerScriptPage(id: string): Promise<AnswerScriptPage> {
  const { data } = await apiClient.get<AnswerScriptPage>(`/answer-script-pages/${id}`);
  return data;
}
