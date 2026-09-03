import { createCrudApi } from "@/api/createCrudApi";
import type { ExamSession, ExamSessionCreate, ExamSessionUpdate } from "@/types/assessment";

export const examSessionsApi = createCrudApi<ExamSession, ExamSessionCreate, ExamSessionUpdate>(
  "/exam-sessions",
);
