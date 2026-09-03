import { createCrudApi } from "@/api/createCrudApi";
import type {
  QuestionBlueprint,
  QuestionBlueprintCreate,
  QuestionBlueprintUpdate,
} from "@/types/assessment";

export const questionBlueprintsApi = createCrudApi<
  QuestionBlueprint,
  QuestionBlueprintCreate,
  QuestionBlueprintUpdate
>("/question-blueprints");
