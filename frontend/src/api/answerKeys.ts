import { createCrudApi } from "@/api/createCrudApi";
import type { AnswerKey, AnswerKeyCreate, AnswerKeyUpdate } from "@/types/assessment";

export const answerKeysApi = createCrudApi<AnswerKey, AnswerKeyCreate, AnswerKeyUpdate>(
  "/answer-keys",
);
