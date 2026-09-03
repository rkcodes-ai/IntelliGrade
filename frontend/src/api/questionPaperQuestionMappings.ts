import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionPaperQuestionMapping,
  QuestionPaperQuestionMappingCreate,
  QuestionPaperQuestionMappingUpdate,
} from "@/types/assessment";

export const questionPaperQuestionMappingsApi = createCrudApi<
  QuestionPaperQuestionMapping,
  QuestionPaperQuestionMappingCreate,
  QuestionPaperQuestionMappingUpdate
>("/question-paper-question-mappings");
