import { createCrudApi } from "@/api/createCrudApi";
import type { Exam, ExamCreate, ExamUpdate } from "@/types/assessment";

export const examsApi = createCrudApi<Exam, ExamCreate, ExamUpdate>("/exams");
