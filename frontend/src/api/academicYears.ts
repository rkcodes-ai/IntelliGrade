import { createCrudApi } from "@/api/createCrudApi";
import type { AcademicYear, AcademicYearCreate, AcademicYearUpdate } from "@/types/academic";

export const academicYearsApi = createCrudApi<AcademicYear, AcademicYearCreate, AcademicYearUpdate>(
  "/academic-years",
);
