import { createCrudApi } from "@/api/createCrudApi";
import type {
  BloomTaxonomyLevel,
  BloomTaxonomyLevelCreate,
  BloomTaxonomyLevelUpdate,
} from "@/types/assessment";

export const bloomTaxonomyLevelsApi = createCrudApi<
  BloomTaxonomyLevel,
  BloomTaxonomyLevelCreate,
  BloomTaxonomyLevelUpdate
>("/bloom-taxonomy-levels");
