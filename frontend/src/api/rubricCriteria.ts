import { createCrudApi } from "@/api/createCrudApi";
import type {
  RubricCriterion,
  RubricCriterionCreate,
  RubricCriterionUpdate,
} from "@/types/assessment";

export const rubricCriteriaApi = createCrudApi<
  RubricCriterion,
  RubricCriterionCreate,
  RubricCriterionUpdate
>("/rubric-criteria");
