import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { BenchmarkReport, OCRProvider, OCRProviderHealth, OCRProviderUpdate } from "@/types/ocr";

/**
 * Read + update only — `backend/app/api/v1/endpoints/ocr_providers.py`
 * has no `POST`/`DELETE` (rows are seeded by migration, see ADR-028).
 */
export async function listOCRProviders(params?: PageParams): Promise<Page<OCRProvider>> {
  const { data } = await apiClient.get<Page<OCRProvider>>("/ocr-providers", { params });
  return data;
}

export async function getOCRProvider(id: string): Promise<OCRProvider> {
  const { data } = await apiClient.get<OCRProvider>(`/ocr-providers/${id}`);
  return data;
}

export async function updateOCRProvider(id: string, payload: OCRProviderUpdate): Promise<OCRProvider> {
  const { data } = await apiClient.patch<OCRProvider>(`/ocr-providers/${id}`, payload);
  return data;
}

/** Live, on-demand health check — always a fresh call against the real adapter, never cached server-side. */
export async function getOCRProviderHealth(id: string): Promise<OCRProviderHealth> {
  const { data } = await apiClient.get<OCRProviderHealth>(`/ocr-providers/${id}/health`);
  return data;
}

/**
 * Runs one uploaded page image through every requested provider and
 * compares accuracy/confidence/performance. `providerCodes` omitted means
 * every registered provider; `referenceText` enables word/character
 * accuracy scoring.
 */
export async function runOCRBenchmark(params: {
  file: File;
  language?: string;
  providerCodes?: string[];
  referenceText?: string;
}): Promise<BenchmarkReport> {
  const formData = new FormData();
  formData.append("file", params.file);
  formData.append("language", params.language ?? "eng");
  if (params.providerCodes?.length) {
    formData.append("provider_codes", params.providerCodes.join(","));
  }
  if (params.referenceText) {
    formData.append("reference_text", params.referenceText);
  }
  const { data } = await apiClient.post<BenchmarkReport>("/ocr-providers/benchmark", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
