import { useQuery } from "@tanstack/react-query";

import { useAppSelector } from "@/store";
import type { Page } from "@/types/pagination";

/**
 * Fetches up to 200 rows of a tenant-scoped entity for populating a
 * `<select>` of parent/related records on a create/edit form (e.g. picking
 * a Campus when creating a Department). Not paginated — these are lookup
 * lists, not primary browsing tables.
 */
export function useSelectOptions<T>(queryKey: string, fetcher: () => Promise<Page<T>>) {
  const institutionId = useAppSelector((state) => state.institution.currentInstitutionId);

  return useQuery({
    queryKey: [queryKey, "options", institutionId],
    queryFn: fetcher,
    enabled: Boolean(institutionId),
    select: (page) => page.items,
    staleTime: 60_000,
  });
}
