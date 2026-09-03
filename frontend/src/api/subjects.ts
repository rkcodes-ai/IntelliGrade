import { createCrudApi } from "@/api/createCrudApi";
import type { Subject, SubjectCreate, SubjectUpdate } from "@/types/academic";

export const subjectsApi = createCrudApi<Subject, SubjectCreate, SubjectUpdate>("/subjects");
