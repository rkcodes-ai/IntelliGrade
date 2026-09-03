import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { AcademicStatus } from "@/types/academic";

/** Read-only — no dedicated Academic Statuses screen in this module, see `types/academic.ts`. */
export async function listAcademicStatuses(params?: PageParams): Promise<Page<AcademicStatus>> {
  const { data } = await apiClient.get<Page<AcademicStatus>>("/academic-statuses", { params });
  return data;
}
