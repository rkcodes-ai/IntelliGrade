import { createCrudApi } from "@/api/createCrudApi";
import type {
  AssessmentConfiguration,
  AssessmentConfigurationCreate,
  AssessmentConfigurationUpdate,
} from "@/types/assessment";

export const assessmentConfigurationsApi = createCrudApi<
  AssessmentConfiguration,
  AssessmentConfigurationCreate,
  AssessmentConfigurationUpdate
>("/assessment-configurations");
