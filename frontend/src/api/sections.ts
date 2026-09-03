import { createCrudApi } from "@/api/createCrudApi";
import type { Section, SectionCreate, SectionUpdate } from "@/types/academic";

export const sectionsApi = createCrudApi<Section, SectionCreate, SectionUpdate>("/sections");
