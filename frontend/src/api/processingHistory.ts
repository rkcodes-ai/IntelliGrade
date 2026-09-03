import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { ProcessingHistory } from "@/types/ocr";

/**
 * Read-only, append-only: `backend/app/api/v1/endpoints/processing_history.py`
 * exposes only `GET ""`/`GET "/{id}"` — rows are written internally by
 * pipeline/task code via `ProcessingHistoryService.record()`. `GET ""`
 * supports a real server-side `answer_script_id` filter.
 */
export async function listProcessingHistory(
  params?: PageParams & { answer_script_id?: string },
): Promise<Page<ProcessingHistory>> {
  const { data } = await apiClient.get<Page<ProcessingHistory>>("/processing-history", { params });
  return data;
}

export async function getProcessingHistory(id: string): Promise<ProcessingHistory> {
  const { data } = await apiClient.get<ProcessingHistory>(`/processing-history/${id}`);
  return data;
}
