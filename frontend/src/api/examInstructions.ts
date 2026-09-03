import { createCrudApi } from "@/api/createCrudApi";
import type {
  ExamInstructions,
  ExamInstructionsCreate,
  ExamInstructionsUpdate,
} from "@/types/assessment";

export const examInstructionsApi = createCrudApi<
  ExamInstructions,
  ExamInstructionsCreate,
  ExamInstructionsUpdate
>("/exam-instructions");
