import { createCrudApi } from "@/api/createCrudApi";
import type { Assessment, AssessmentCreate, AssessmentUpdate } from "@/types/assessment";

export const assessmentsApi = createCrudApi<Assessment, AssessmentCreate, AssessmentUpdate>(
  "/assessments",
);
