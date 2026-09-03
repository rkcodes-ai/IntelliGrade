import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAppSelector } from "@/store";
import type { Page, PageParams, SortOrder } from "@/types/pagination";

interface UsePaginatedListOptions<TRead> {
  /** Query-key namespace for this entity, e.g. "campuses". */
  queryKey: string;
  fetcher: (params: PageParams) => Promise<Page<TRead>>;
  defaultPageSize?: number;
  defaultSortBy?: string;
  /** Include the deleted-only variant (soft-deleted records view) instead of the live list. */
  deleted?: boolean;
  /**
   * Whether this entity is tenant-scoped and must wait for a current
   * institution to be selected before fetching. Institution itself is the
   * tenant root and has no such requirement — its list page must be usable
   * even before any institution has been created/selected.
   */
  requiresInstitution?: boolean;
}

/**
 * Drives one entity's paginated/searchable/sortable list against the
 * backend's real `Page[T]`/`PageParams` contract. Keyed by the current
 * institution so switching tenants never shows stale cross-tenant results
 * from the cache (see `store/slices/institutionSlice.ts`).
 */
export function usePaginatedList<TRead>({
  queryKey,
  fetcher,
  defaultPageSize = 20,
  defaultSortBy = "created_at",
  deleted = false,
  requiresInstitution = true,
}: UsePaginatedListOptions<TRead>) {
  const institutionId = useAppSelector((state) => state.institution.currentInstitutionId);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState(defaultSortBy);
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const params: PageParams = {
    page,
    page_size: pageSize,
    search: search || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  };

  const query = useQuery({
    queryKey: [queryKey, deleted ? "deleted" : "list", institutionId, params],
    queryFn: () => fetcher(params),
    enabled: requiresInstitution ? Boolean(institutionId) : true,
    placeholderData: (previous) => previous,
  });

  function updateSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function updatePageSize(value: number) {
    setPageSize(value);
    setPage(1);
  }

  function toggleSort(field: string) {
    if (sortBy === field) {
      setSortOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
    setPage(1);
  }

  return {
    data: query.data,
    items: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    totalPages: query.data?.total_pages ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    isFetching: query.isFetching,
    page,
    pageSize,
    search,
    sortBy,
    sortOrder,
    setPage,
    setSearch: updateSearch,
    setPageSize: updatePageSize,
    toggleSort,
    refetch: query.refetch,
  };
}
