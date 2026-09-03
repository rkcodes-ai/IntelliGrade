import { createCrudApi } from "@/api/createCrudApi";
import type {
  TeacherAssignment,
  TeacherAssignmentCreate,
  TeacherAssignmentUpdate,
} from "@/types/academic";

export const teacherAssignmentsApi = createCrudApi<
  TeacherAssignment,
  TeacherAssignmentCreate,
  TeacherAssignmentUpdate
>("/teacher-assignments");
