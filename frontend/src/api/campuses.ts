import { createCrudApi } from "@/api/createCrudApi";
import type { Campus, CampusCreate, CampusUpdate } from "@/types/academic";

export const campusesApi = createCrudApi<Campus, CampusCreate, CampusUpdate>("/campuses");
