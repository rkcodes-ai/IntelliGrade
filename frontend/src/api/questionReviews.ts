import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionReview,
  QuestionReviewCreate,
  QuestionReviewUpdate,
} from "@/types/assessment";

export const questionReviewsApi = createCrudApi<
  QuestionReview,
  QuestionReviewCreate,
  QuestionReviewUpdate
>("/question-reviews");
