import { createCrudApi } from "@/api/createCrudApi";
import type { Rubric, RubricCreate, RubricUpdate } from "@/types/assessment";

export const rubricsApi = createCrudApi<Rubric, RubricCreate, RubricUpdate>("/rubrics");
