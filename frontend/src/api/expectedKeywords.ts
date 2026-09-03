import { createCrudApi } from "@/api/createCrudApi";
import type {
  ExpectedKeyword,
  ExpectedKeywordCreate,
  ExpectedKeywordUpdate,
} from "@/types/assessment";

export const expectedKeywordsApi = createCrudApi<
  ExpectedKeyword,
  ExpectedKeywordCreate,
  ExpectedKeywordUpdate
>("/expected-keywords");
