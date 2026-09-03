import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { SubjectAllocation } from "@/types/academic";

/** Read-only — no dedicated Subject Allocations screen in this module, see `types/academic.ts`. */
export async function listSubjectAllocations(params?: PageParams): Promise<Page<SubjectAllocation>> {
  const { data } = await apiClient.get<Page<SubjectAllocation>>("/subject-allocations", { params });
  return data;
}
