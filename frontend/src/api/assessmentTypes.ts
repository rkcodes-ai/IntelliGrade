import { createCrudApi } from "@/api/createCrudApi";
import type { AssessmentType, AssessmentTypeCreate, AssessmentTypeUpdate } from "@/types/assessment";

export const assessmentTypesApi = createCrudApi<AssessmentType, AssessmentTypeCreate, AssessmentTypeUpdate>(
  "/assessment-types",
);
