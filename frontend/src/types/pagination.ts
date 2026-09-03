/**
 * Mirrors the backend's `Page[T]` response envelope and `PageParams`
 * request shape (`backend/app/schemas/pagination.py`) — the first frontend
 * consumer of this contract (Module 02's `listUsers` predates it and uses
 * a bare array with `limit`/`offset`, see `api/users.ts`).
 */

export type SortOrder = "asc" | "desc";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PageParams {
  page?: number;
  page_size?: number;
  search?: string;
  sort_by?: string;
  sort_order?: SortOrder;
}
