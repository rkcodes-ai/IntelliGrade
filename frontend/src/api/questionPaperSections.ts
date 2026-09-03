import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionPaperSection,
  QuestionPaperSectionCreate,
  QuestionPaperSectionUpdate,
} from "@/types/assessment";

export const questionPaperSectionsApi = createCrudApi<
  QuestionPaperSection,
  QuestionPaperSectionCreate,
  QuestionPaperSectionUpdate
>("/question-paper-sections");
