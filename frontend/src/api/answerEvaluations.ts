import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type {
  AnswerEvaluation,
  AnswerEvaluationOverride,
  AnswerEvaluationReject,
  AnswerEvaluationTrigger,
} from "@/types/officialExam";

/**
 * `POST ""` triggers `AnswerEvaluationService.evaluate_question()` — not a
 * raw create, every score field is AI-computed server-side. `confirm`/
 * `override` are the two Teacher Review actions (ADR-040). See
 * `backend/app/api/v1/endpoints/answer_evaluations.py`.
 */
export async function listAnswerEvaluations(params?: PageParams): Promise<Page<AnswerEvaluation>> {
  const { data } = await apiClient.get<Page<AnswerEvaluation>>("/answer-evaluations", { params });
  return data;
}

export async function getAnswerEvaluation(id: string): Promise<AnswerEvaluation> {
  const { data } = await apiClient.get<AnswerEvaluation>(`/answer-evaluations/${id}`);
  return data;
}

export async function triggerAnswerEvaluation(
  payload: AnswerEvaluationTrigger,
): Promise<AnswerEvaluation> {
  const { data } = await apiClient.post<AnswerEvaluation>("/answer-evaluations", payload);
  return data;
}

export async function confirmAnswerEvaluation(id: string): Promise<AnswerEvaluation> {
  const { data } = await apiClient.post<AnswerEvaluation>(`/answer-evaluations/${id}/confirm`);
  return data;
}

export async function overrideAnswerEvaluation(
  id: string,
  payload: AnswerEvaluationOverride,
): Promise<AnswerEvaluation> {
  const { data } = await apiClient.post<AnswerEvaluation>(
    `/answer-evaluations/${id}/override`,
    payload,
  );
  return data;
}

/** Teacher Review action (Module 07, ADR-043): discard this AI evaluation
 * entirely. `suggested_marks` is left untouched; only `final_marks` is
 * cleared. */
export async function rejectAnswerEvaluation(
  id: string,
  payload: AnswerEvaluationReject,
): Promise<AnswerEvaluation> {
  const { data } = await apiClient.post<AnswerEvaluation>(
    `/answer-evaluations/${id}/reject`,
    payload,
  );
  return data;
}

/** Teacher Review action (Module 07, ADR-043): force a fresh AI
 * evaluation even over an already-reviewed row. */
export async function rerunAnswerEvaluation(id: string): Promise<AnswerEvaluation> {
  const { data } = await apiClient.post<AnswerEvaluation>(`/answer-evaluations/${id}/rerun`);
  return data;
}
