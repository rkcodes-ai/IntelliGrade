import { Eye } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { listAIReferenceAnswers } from "@/api/aiReferenceAnswers";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import type { AIReferenceAnswer } from "@/types/aiReferenceAnswer";

/**
 * Landing screen for the AI Reference Answer Builder milestone: a
 * paginated list of every `AIReferenceAnswer` (current and historical
 * versions) across the institution. Each row links to the per-question,
 * three-column review screen (`AIReferenceAnswerReviewPage`) where
 * generation/approval/rejection/regeneration actually happen — this page
 * is deliberately read-only, same "list here, act on the detail page"
 * split as `EvaluationReviewDashboardPage` / `AnswerEvaluationDetailPage`.
 */
export function AIReferenceAnswerDashboardPage() {
  const navigate = useNavigate();

  const list = usePaginatedList<AIReferenceAnswer>({
    queryKey: "ai-reference-answers",
    fetcher: (params) => listAIReferenceAnswers(params),
  });

  const columns: Column<AIReferenceAnswer>[] = [
    { key: "extracted_question_id", header: "Extracted Question", render: (row) => row.extracted_question_id },
    { key: "version", header: "Version", render: (row) => row.version },
    {
      key: "is_current",
      header: "Current?",
      render: (row) => (row.is_current ? <Badge variant="primary">Current</Badge> : "—"),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <Badge variant={statusVariant(row.status)}>{formatStatusLabel(row.status)}</Badge>
      ),
    },
    {
      key: "generation_confidence",
      header: "Confidence",
      render: (row) => (row.generation_confidence != null ? `${row.generation_confidence}%` : "—"),
    },
    { key: "maximum_marks", header: "Max Marks", render: (row) => row.maximum_marks },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="AI Reference Answers"
        description="AI-synthesized evaluation references built from official model answers, awaiting or holding teacher verification."
      />

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No AI reference answers found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Review AI reference answer for question ${row.extracted_question_id}`}
              onClick={() =>
                navigate(
                  `/dashboard/extracted-questions/${row.extracted_question_id}/ai-reference-answer`,
                )
              }
            >
              <Eye className="h-4 w-4" />
            </Button>
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
