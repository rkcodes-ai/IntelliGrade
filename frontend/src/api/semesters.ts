import { createCrudApi } from "@/api/createCrudApi";
import type { Semester, SemesterCreate, SemesterUpdate } from "@/types/academic";

export const semestersApi = createCrudApi<Semester, SemesterCreate, SemesterUpdate>("/semesters");
