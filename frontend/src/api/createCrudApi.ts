/**
 * Generic factory for the Academic Domain's uniform REST shape (every
 * Module 03 entity endpoint follows the same pattern — see e.g.
 * `backend/app/api/v1/endpoints/campuses.py`): paginated list, get, create,
 * update, soft-delete, restore, list-deleted. Introduced here rather than
 * hand-writing ~11 near-identical API modules (Module 02's `api/users.ts`
 * etc. predate this convention and are single hand-written modules, which
 * was fine for one entity but doesn't scale to eleven near-identical ones).
 */
import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";

export interface CrudApi<TRead, TCreate, TUpdate> {
  list(params?: PageParams): Promise<Page<TRead>>;
  listDeleted(params?: PageParams): Promise<Page<TRead>>;
  get(id: string): Promise<TRead>;
  create(data: TCreate): Promise<TRead>;
  update(id: string, data: TUpdate): Promise<TRead>;
  remove(id: string): Promise<void>;
  restore(id: string): Promise<TRead>;
}

export function createCrudApi<TRead, TCreate, TUpdate>(basePath: string): CrudApi<TRead, TCreate, TUpdate> {
  return {
    async list(params) {
      const { data } = await apiClient.get<Page<TRead>>(basePath, { params });
      return data;
    },
    async listDeleted(params) {
      const { data } = await apiClient.get<Page<TRead>>(`${basePath}/deleted`, { params });
      return data;
    },
    async get(id) {
      const { data } = await apiClient.get<TRead>(`${basePath}/${id}`);
      return data;
    },
    async create(payload) {
      const { data } = await apiClient.post<TRead>(basePath, payload);
      return data;
    },
    async update(id, payload) {
      const { data } = await apiClient.patch<TRead>(`${basePath}/${id}`, payload);
      return data;
    },
    async remove(id) {
      await apiClient.delete(`${basePath}/${id}`);
    },
    async restore(id) {
      const { data } = await apiClient.post<TRead>(`${basePath}/${id}/restore`);
      return data;
    },
  };
}
