import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionBlueprintSection,
  QuestionBlueprintSectionCreate,
  QuestionBlueprintSectionUpdate,
} from "@/types/assessment";

export const questionBlueprintSectionsApi = createCrudApi<
  QuestionBlueprintSection,
  QuestionBlueprintSectionCreate,
  QuestionBlueprintSectionUpdate
>("/question-blueprint-sections");
