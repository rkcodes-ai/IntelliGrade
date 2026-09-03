import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionCategory,
  QuestionCategoryCreate,
  QuestionCategoryUpdate,
} from "@/types/assessment";

export const questionCategoriesApi = createCrudApi<
  QuestionCategory,
  QuestionCategoryCreate,
  QuestionCategoryUpdate
>("/question-categories");
