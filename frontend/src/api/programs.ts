import { createCrudApi } from "@/api/createCrudApi";
import type { Program, ProgramCreate, ProgramUpdate } from "@/types/academic";

export const programsApi = createCrudApi<Program, ProgramCreate, ProgramUpdate>("/programs");
