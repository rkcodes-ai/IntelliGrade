import { useState } from "react";
import { Eye, Pencil, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { bloomTaxonomyLevelsApi } from "@/api/bloomTaxonomyLevels";
import { difficultyLevelsApi } from "@/api/difficultyLevels";
import { questionCategoriesApi } from "@/api/questionCategories";
import { questionTypesApi } from "@/api/questionTypes";
import { questionsApi } from "@/api/questions";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { useAppSelector } from "@/store";
import type { ApprovalStatus, Question } from "@/types/assessment";

const APPROVAL_STATUSES: ApprovalStatus[] = [
  "draft",
  "pending_review",
  "approved",
  "rejected",
  "archived",
];

function truncate(text: string, length = 60) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

const approvalStatusClassName: Record<ApprovalStatus, string> = {
  draft: "text-muted-foreground",
  pending_review: "text-warning",
  approved: "text-primary",
  rejected: "text-destructive",
  archived: "text-muted-foreground",
};

/**
 * Browse/search/filter grid over the `Question` entity. Create/edit and the
 * read-only detail view live on separate screens (Question Editor / Question
 * Viewer) built in parallel — this page only lists rows and navigates.
 */
export function QuestionBankDashboardPage() {
  const navigate = useNavigate();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("questions:create");
  const canUpdate = permissions.includes("questions:update");

  const list = usePaginatedList<Question>({
    queryKey: "questions",
    fetcher: (params) => questionsApi.list(params),
  });
  const { data: categories } = useSelectOptions("question-categories", () =>
    questionCategoriesApi.list({ page_size: 200 }),
  );
  const { data: types } = useSelectOptions("question-types", () =>
    questionTypesApi.list({ page_size: 200 }),
  );
  const { data: difficulties } = useSelectOptions("difficulty-levels", () =>
    difficultyLevelsApi.list({ page_size: 200 }),
  );
  const { data: bloomLevels } = useSelectOptions("bloom-taxonomy-levels", () =>
    bloomTaxonomyLevelsApi.list({ page_size: 200 }),
  );

  const [categoryFilter, setCategoryFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [bloomFilter, setBloomFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const categoryName = (id: string) => categories?.find((c) => c.id === id)?.name ?? id;
  const typeName = (id: string) => types?.find((t) => t.id === id)?.name ?? id;
  const difficultyName = (id: string) => difficulties?.find((d) => d.id === id)?.name ?? id;
  const bloomName = (id: string) => bloomLevels?.find((b) => b.id === id)?.name ?? id;

  const filteredItems = list.items.filter(
    (question) =>
      (!categoryFilter || question.question_category_id === categoryFilter) &&
      (!typeFilter || question.question_type_id === typeFilter) &&
      (!difficultyFilter || question.difficulty_level_id === difficultyFilter) &&
      (!bloomFilter || question.bloom_level_id === bloomFilter) &&
      (!statusFilter || question.approval_status === statusFilter),
  );

  const columns: Column<Question>[] = [
    { key: "question_text", header: "Question Text", render: (row) => truncate(row.question_text) },
    { key: "category", header: "Category", render: (row) => categoryName(row.question_category_id) },
    { key: "type", header: "Type", render: (row) => typeName(row.question_type_id) },
    { key: "difficulty", header: "Difficulty", render: (row) => difficultyName(row.difficulty_level_id) },
    { key: "bloom", header: "Bloom Level", render: (row) => bloomName(row.bloom_level_id) },
    { key: "marks", header: "Marks", render: (row) => row.marks },
    {
      key: "approval_status",
      header: "Approval Status",
      render: (row) => (
        <span className={approvalStatusClassName[row.approval_status]}>
          {row.approval_status.replace("_", " ")}
        </span>
      ),
    },
    { key: "version", header: "Version", render: (row) => `v${row.current_version}` },
  ];

  return (
    <div>
      <PageHeader
        title="Question Bank"
        description="Search, filter, and browse questions in the question bank."
        actions={
          canCreate && (
            <Button onClick={() => navigate("/dashboard/questions/new")}>
              <Plus className="h-4 w-4" />
              New Question
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search questions..." />
        <Select
          aria-label="Filter by category"
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(event.target.value)}
          className="w-auto"
        >
          <option value="">All Categories</option>
          {categories?.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by type"
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value)}
          className="w-auto"
        >
          <option value="">All Types</option>
          {types?.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by difficulty"
          value={difficultyFilter}
          onChange={(event) => setDifficultyFilter(event.target.value)}
          className="w-auto"
        >
          <option value="">All Difficulties</option>
          {difficulties?.map((difficulty) => (
            <option key={difficulty.id} value={difficulty.id}>
              {difficulty.name}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by Bloom level"
          value={bloomFilter}
          onChange={(event) => setBloomFilter(event.target.value)}
          className="w-auto"
        >
          <option value="">All Bloom Levels</option>
          {bloomLevels?.map((bloomLevel) => (
            <option key={bloomLevel.id} value={bloomLevel.id}>
              {bloomLevel.name}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by approval status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="w-auto"
        >
          <option value="">All Statuses</option>
          {APPROVAL_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace("_", " ")}
            </option>
          ))}
        </Select>
      </div>

      <DataTable
        columns={columns}
        rows={filteredItems}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No questions found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`View ${truncate(row.question_text, 30)}`}
              onClick={() => navigate(`/dashboard/questions/${row.id}`)}
            >
              <Eye className="h-4 w-4" />
            </Button>
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit ${truncate(row.question_text, 30)}`}
                onClick={() => navigate(`/dashboard/questions/${row.id}/edit`)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      />

      <PaginationControls
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        totalPages={list.totalPages}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />
    </div>
  );
}
