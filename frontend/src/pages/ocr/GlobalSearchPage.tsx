import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { globalSearch } from "@/api/search";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchInput } from "@/components/common/SearchInput";
import { Spinner } from "@/components/ui/spinner";
import type { SearchResultItem, SearchResultType } from "@/types/teacherReview";

const TYPE_LABELS: Record<SearchResultType, string> = {
  student: "Students",
  teacher: "Teachers",
  subject: "Subjects",
  question: "Questions",
  evaluation: "Evaluations",
};

const TYPE_ORDER: SearchResultType[] = ["student", "teacher", "subject", "question", "evaluation"];

/**
 * Global Search screen (Module 07, Feature 9): a single debounced search box
 * that queries `GET /search` across students, teachers, subjects, questions,
 * and evaluations, and renders the results grouped by type.
 */
export function GlobalSearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const trimmedQuery = query.trim();

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["search", query],
    queryFn: () => globalSearch(query),
    enabled: trimmedQuery.length > 0,
  });

  const results = data?.results ?? [];
  const grouped = new Map<SearchResultType, SearchResultItem[]>();
  for (const result of results) {
    const bucket = grouped.get(result.type);
    if (bucket) {
      bucket.push(result);
    } else {
      grouped.set(result.type, [result]);
    }
  }

  function handleResultClick(result: SearchResultItem) {
    if (result.type === "evaluation") {
      navigate(`/dashboard/answer-evaluations/${result.id}`);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Global Search"
        description="Search across students, teachers, subjects, questions, and evaluations."
      />

      <SearchInput
        value={query}
        onChange={setQuery}
        placeholder="Search for students, teachers, subjects, questions, or evaluations..."
      />

      {trimmedQuery.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Search for students, teachers, subjects, questions, or evaluations.
        </p>
      )}

      {trimmedQuery.length > 0 && (isLoading || isFetching) && (
        <div className="flex justify-center p-12">
          <Spinner />
        </div>
      )}

      {trimmedQuery.length > 0 && !isLoading && !isFetching && results.length === 0 && (
        <p className="text-sm text-muted-foreground">No results found for &quot;{query}&quot;.</p>
      )}

      {trimmedQuery.length > 0 && !isLoading && !isFetching && results.length > 0 && (
        <div className="flex flex-col gap-6">
          {TYPE_ORDER.filter((type) => (grouped.get(type)?.length ?? 0) > 0).map((type) => (
            <div key={type}>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {TYPE_LABELS[type]}
              </h2>
              <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
                {grouped.get(type)!.map((result) => {
                  const clickable = result.type === "evaluation";
                  return (
                    <li key={result.id}>
                      {clickable ? (
                        <button
                          type="button"
                          onClick={() => handleResultClick(result)}
                          className="flex w-full flex-col gap-0.5 px-4 py-3 text-left text-sm hover:bg-secondary"
                        >
                          <span className="font-medium">{result.label}</span>
                          {result.subtitle && (
                            <span className="text-xs text-muted-foreground">{result.subtitle}</span>
                          )}
                        </button>
                      ) : (
                        <div className="flex flex-col gap-0.5 px-4 py-3 text-sm">
                          <span className="font-medium">{result.label}</span>
                          {result.subtitle && (
                            <span className="text-xs text-muted-foreground">{result.subtitle}</span>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
