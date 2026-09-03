import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { SubjectCategory } from "@/types/academic";

/** Read-only — no dedicated Subject Categories screen in this module, see `types/academic.ts`. */
export async function listSubjectCategories(params?: PageParams): Promise<Page<SubjectCategory>> {
  const { data } = await apiClient.get<Page<SubjectCategory>>("/subject-categories", { params });
  return data;
}
