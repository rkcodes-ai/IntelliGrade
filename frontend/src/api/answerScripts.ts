import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { AnswerScript, AnswerScriptUpdate } from "@/types/ocr";

/**
 * Not a `createCrudApi` object — `POST ""` takes multipart form data (a
 * file + `exam_session_id`), not a JSON body, and there's no client-facing
 * create schema to type it with (see `backend/app/api/v1/endpoints/
 * answer_scripts.py`).
 */
export async function listAnswerScripts(params?: PageParams): Promise<Page<AnswerScript>> {
  const { data } = await apiClient.get<Page<AnswerScript>>("/answer-scripts", { params });
  return data;
}

export async function listDeletedAnswerScripts(params?: PageParams): Promise<Page<AnswerScript>> {
  const { data } = await apiClient.get<Page<AnswerScript>>("/answer-scripts/deleted", { params });
  return data;
}

export async function getAnswerScript(id: string): Promise<AnswerScript> {
  const { data } = await apiClient.get<AnswerScript>(`/answer-scripts/${id}`);
  return data;
}

export async function uploadAnswerScript(
  examSessionId: string,
  file: File,
  options?: { allowDuplicate?: boolean },
): Promise<AnswerScript> {
  const form = new FormData();
  form.append("exam_session_id", examSessionId);
  form.append("file", file);
  if (options?.allowDuplicate) form.append("allow_duplicate", "true");

  const { data } = await apiClient.post<AnswerScript>("/answer-scripts", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function bulkUploadAnswerScripts(
  examSessionId: string,
  files: File[],
): Promise<{ created: number; errors: { index: number; filename: string; error: string }[] }> {
  const form = new FormData();
  form.append("exam_session_id", examSessionId);
  files.forEach((file) => form.append("files", file));

  const { data } = await apiClient.post<{
    created: number;
    errors: { index: number; filename: string; error: string }[];
  }>("/answer-scripts/bulk", form, { headers: { "Content-Type": "multipart/form-data" } });
  return data;
}

export async function updateAnswerScript(id: string, payload: AnswerScriptUpdate): Promise<AnswerScript> {
  const { data } = await apiClient.patch<AnswerScript>(`/answer-scripts/${id}`, payload);
  return data;
}

export async function removeAnswerScript(id: string): Promise<void> {
  await apiClient.delete(`/answer-scripts/${id}`);
}

export async function restoreAnswerScript(id: string): Promise<AnswerScript> {
  const { data } = await apiClient.post<AnswerScript>(`/answer-scripts/${id}/restore`);
  return data;
}

export async function retryAnswerScript(id: string): Promise<AnswerScript> {
  const { data } = await apiClient.post<AnswerScript>(`/answer-scripts/${id}/retry`);
  return data;
}

export async function cancelAnswerScript(id: string): Promise<AnswerScript> {
  const { data } = await apiClient.post<AnswerScript>(`/answer-scripts/${id}/cancel`);
  return data;
}

export async function downloadAnswerScript(id: string): Promise<{ url: string }> {
  const { data } = await apiClient.get<{ url: string }>(`/answer-scripts/${id}/download`);
  return data;
}
