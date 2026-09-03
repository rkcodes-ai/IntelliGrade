import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { Batch } from "@/types/academic";

/** Read-only — no dedicated Batches screen in this module, see `types/academic.ts`. */
export async function listBatches(params?: PageParams): Promise<Page<Batch>> {
  const { data } = await apiClient.get<Page<Batch>>("/batches", { params });
  return data;
}
