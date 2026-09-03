import { createCrudApi } from "@/api/createCrudApi";
import type {
  EvaluationConfiguration,
  EvaluationConfigurationCreate,
  EvaluationConfigurationUpdate,
} from "@/types/assessment";

export const evaluationConfigurationsApi = createCrudApi<
  EvaluationConfiguration,
  EvaluationConfigurationCreate,
  EvaluationConfigurationUpdate
>("/evaluation-configurations");
