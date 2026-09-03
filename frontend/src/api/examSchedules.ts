import { createCrudApi } from "@/api/createCrudApi";
import type { ExamSchedule, ExamScheduleCreate, ExamScheduleUpdate } from "@/types/assessment";

export const examSchedulesApi = createCrudApi<ExamSchedule, ExamScheduleCreate, ExamScheduleUpdate>(
  "/exam-schedules",
);
