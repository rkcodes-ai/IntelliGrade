import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { OCRJob, OCRJobCreate } from "@/types/ocr";

/**
 * Not a `createCrudApi` object — no `PATCH`/`DELETE`/restore
 * (`backend/app/api/v1/endpoints/ocr_jobs.py` only has `GET`/`POST ""`/
 * `POST "/{id}/cancel"`). No server-side `answer_script_id` filter exists
 * either — a screen needing "jobs for this script" fetches a page and
 * filters client-side, same convention as `types/assessment.ts`'s
 * client-side-filtered screens.
 */
export async function listOCRJobs(params?: PageParams): Promise<Page<OCRJob>> {
  const { data } = await apiClient.get<Page<OCRJob>>("/ocr-jobs", { params });
  return data;
}

export async function getOCRJob(id: string): Promise<OCRJob> {
  const { data } = await apiClient.get<OCRJob>(`/ocr-jobs/${id}`);
  return data;
}

export async function createOCRJob(payload: OCRJobCreate): Promise<OCRJob> {
  const { data } = await apiClient.post<OCRJob>("/ocr-jobs", payload);
  return data;
}

export async function cancelOCRJob(id: string): Promise<OCRJob> {
  const { data } = await apiClient.post<OCRJob>(`/ocr-jobs/${id}/cancel`);
  return data;
}
