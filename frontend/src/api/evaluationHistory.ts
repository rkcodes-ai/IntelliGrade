import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { EvaluationHistory, EvaluationHistoryCreate } from "@/types/assessment";

/**
 * `backend/app/api/v1/endpoints/evaluation_history.py` only wires
 * `GET ""`, `GET "/{id}"`, and `POST ""` — no `PATCH`/`DELETE`/`restore`
 * permission codes exist for this entity, so this is NOT a `createCrudApi`
 * object.
 */
export async function listEvaluationHistory(params?: PageParams): Promise<Page<EvaluationHistory>> {
  const { data } = await apiClient.get<Page<EvaluationHistory>>("/evaluation-history", { params });
  return data;
}

export async function getEvaluationHistory(id: string): Promise<EvaluationHistory> {
  const { data } = await apiClient.get<EvaluationHistory>(`/evaluation-history/${id}`);
  return data;
}

export async function createEvaluationHistory(
  payload: EvaluationHistoryCreate,
): Promise<EvaluationHistory> {
  const { data } = await apiClient.post<EvaluationHistory>("/evaluation-history", payload);
  return data;
}
