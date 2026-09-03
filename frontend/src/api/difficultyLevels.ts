import { createCrudApi } from "@/api/createCrudApi";
import type {
  DifficultyLevel,
  DifficultyLevelCreate,
  DifficultyLevelUpdate,
} from "@/types/assessment";

export const difficultyLevelsApi = createCrudApi<
  DifficultyLevel,
  DifficultyLevelCreate,
  DifficultyLevelUpdate
>("/difficulty-levels");
