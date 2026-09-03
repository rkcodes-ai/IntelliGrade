import { createCrudApi } from "@/api/createCrudApi";
import type { OCRConfiguration, OCRConfigurationCreate, OCRConfigurationUpdate } from "@/types/ocr";

export const ocrConfigurationsApi = createCrudApi<
  OCRConfiguration,
  OCRConfigurationCreate,
  OCRConfigurationUpdate
>("/ocr-configurations");
