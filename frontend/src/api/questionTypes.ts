import { createCrudApi } from "@/api/createCrudApi";
import type { QuestionType, QuestionTypeCreate, QuestionTypeUpdate } from "@/types/assessment";

export const questionTypesApi = createCrudApi<QuestionType, QuestionTypeCreate, QuestionTypeUpdate>(
  "/question-types",
);
