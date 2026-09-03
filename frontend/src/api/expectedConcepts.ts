import { createCrudApi } from "@/api/createCrudApi";
import type {
  ExpectedConcept,
  ExpectedConceptCreate,
  ExpectedConceptUpdate,
} from "@/types/assessment";

export const expectedConceptsApi = createCrudApi<
  ExpectedConcept,
  ExpectedConceptCreate,
  ExpectedConceptUpdate
>("/expected-concepts");
