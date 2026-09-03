import { apiClient } from "@/api/client";
import type { SearchResults } from "@/types/teacherReview";

/** Global Search (Module 07, Feature 9). See
 * `backend/app/api/v1/endpoints/search.py`. */
export async function globalSearch(query: string): Promise<SearchResults> {
  const { data } = await apiClient.get<SearchResults>("/search", { params: { q: query } });
  return data;
}
