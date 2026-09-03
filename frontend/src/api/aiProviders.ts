import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { AIProvider, AIProviderUpdate } from "@/types/officialExam";

/**
 * Read + update only — `backend/app/api/v1/endpoints/ai_providers.py`
 * has no `POST`/`DELETE` (rows are seeded by migration, see ADR-041).
 */
export async function listAIProviders(params?: PageParams): Promise<Page<AIProvider>> {
  const { data } = await apiClient.get<Page<AIProvider>>("/ai-providers", { params });
  return data;
}

export async function getAIProvider(id: string): Promise<AIProvider> {
  const { data } = await apiClient.get<AIProvider>(`/ai-providers/${id}`);
  return data;
}

export async function updateAIProvider(id: string, payload: AIProviderUpdate): Promise<AIProvider> {
  const { data } = await apiClient.patch<AIProvider>(`/ai-providers/${id}`, payload);
  return data;
}
