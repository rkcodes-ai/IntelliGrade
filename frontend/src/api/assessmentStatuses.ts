import { createCrudApi } from "@/api/createCrudApi";
import type {
  AssessmentStatus,
  AssessmentStatusCreate,
  AssessmentStatusUpdate,
} from "@/types/assessment";

export const assessmentStatusesApi = createCrudApi<
  AssessmentStatus,
  AssessmentStatusCreate,
  AssessmentStatusUpdate
>("/assessment-statuses");
