import { createCrudApi } from "@/api/createCrudApi";
import type { AIConfiguration, AIConfigurationCreate, AIConfigurationUpdate } from "@/types/officialExam";

export const aiConfigurationsApi = createCrudApi<
  AIConfiguration,
  AIConfigurationCreate,
  AIConfigurationUpdate
>("/ai-configurations");
