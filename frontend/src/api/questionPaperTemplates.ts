import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionPaperTemplate,
  QuestionPaperTemplateCreate,
  QuestionPaperTemplateUpdate,
} from "@/types/assessment";

export const questionPaperTemplatesApi = createCrudApi<
  QuestionPaperTemplate,
  QuestionPaperTemplateCreate,
  QuestionPaperTemplateUpdate
>("/question-paper-templates");
