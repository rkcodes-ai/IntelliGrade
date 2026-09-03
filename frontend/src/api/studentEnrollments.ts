import { createCrudApi } from "@/api/createCrudApi";
import type {
  StudentEnrollment,
  StudentEnrollmentCreate,
  StudentEnrollmentUpdate,
} from "@/types/academic";

export const studentEnrollmentsApi = createCrudApi<
  StudentEnrollment,
  StudentEnrollmentCreate,
  StudentEnrollmentUpdate
>("/student-enrollments");
