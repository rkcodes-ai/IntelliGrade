import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { UploadJob } from "@/types/ocr";

/**
 * Read-only: rows are created internally by `answerScripts.uploadAnswerScript`
 * on the backend, never via a client-facing `POST` on this router.
 */
export async function listUploadJobs(
  params?: PageParams & { answer_script_id?: string },
): Promise<Page<UploadJob>> {
  const { data } = await apiClient.get<Page<UploadJob>>("/upload-jobs", { params });
  return data;
}

export async function getUploadJob(id: string): Promise<UploadJob> {
  const { data } = await apiClient.get<UploadJob>(`/upload-jobs/${id}`);
  return data;
}
