import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type {
  MarkSchemeExpansionResponse,
  MarkSchemeRange,
  MarkSchemeRangeUpdate,
} from "@/types/officialExam";

/**
 * No `POST ""`/`DELETE` — rows are written internally by
 * `app.tasks.official_document_tasks` during ingestion (see
 * `backend/app/api/v1/endpoints/mark_scheme_ranges.py`). `expandMarkScheme`
 * calls the data-driven range -> per-question-marks expansion — never a
 * hardcoded range in application code, per the brief's own requirement.
 */
export async function listMarkSchemeRanges(
  params?: PageParams & { document_id?: string },
): Promise<Page<MarkSchemeRange>> {
  const { data } = await apiClient.get<Page<MarkSchemeRange>>("/mark-scheme-ranges", { params });
  return data;
}

export async function getMarkSchemeRange(id: string): Promise<MarkSchemeRange> {
  const { data } = await apiClient.get<MarkSchemeRange>(`/mark-scheme-ranges/${id}`);
  return data;
}

export async function updateMarkSchemeRange(
  id: string,
  payload: MarkSchemeRangeUpdate,
): Promise<MarkSchemeRange> {
  const { data } = await apiClient.patch<MarkSchemeRange>(`/mark-scheme-ranges/${id}`, payload);
  return data;
}

export async function verifyMarkSchemeRange(id: string): Promise<MarkSchemeRange> {
  const { data } = await apiClient.post<MarkSchemeRange>(`/mark-scheme-ranges/${id}/verify`);
  return data;
}

export async function expandMarkScheme(documentId: string): Promise<MarkSchemeExpansionResponse> {
  const { data } = await apiClient.get<MarkSchemeExpansionResponse>("/mark-scheme-ranges/expand", {
    params: { document_id: documentId },
  });
  return data;
}
