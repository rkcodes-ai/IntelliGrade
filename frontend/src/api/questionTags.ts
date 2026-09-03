import { createCrudApi } from "@/api/createCrudApi";
import type { QuestionTag, QuestionTagCreate, QuestionTagUpdate } from "@/types/assessment";

export const questionTagsApi = createCrudApi<QuestionTag, QuestionTagCreate, QuestionTagUpdate>(
  "/question-tags",
);
