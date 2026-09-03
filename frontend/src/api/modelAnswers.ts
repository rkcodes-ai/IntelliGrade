import { createCrudApi } from "@/api/createCrudApi";
import type { ModelAnswer, ModelAnswerCreate, ModelAnswerUpdate } from "@/types/assessment";

export const modelAnswersApi = createCrudApi<ModelAnswer, ModelAnswerCreate, ModelAnswerUpdate>(
  "/model-answers",
);
