import { createCrudApi } from "@/api/createCrudApi";
import type {
  AlternativeAnswer,
  AlternativeAnswerCreate,
  AlternativeAnswerUpdate,
} from "@/types/assessment";

export const alternativeAnswersApi = createCrudApi<
  AlternativeAnswer,
  AlternativeAnswerCreate,
  AlternativeAnswerUpdate
>("/alternative-answers");
