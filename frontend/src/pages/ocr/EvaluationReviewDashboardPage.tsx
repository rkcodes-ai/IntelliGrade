import { useState, type FormEvent } from "react";
import { Eye } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { listAnswerEvaluations, triggerAnswerEvaluation } from "@/api/answerEvaluations";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { AnswerEvaluation, ConfidenceTier } from "@/types/officialExam";

type TierFilter = ConfidenceTier | "all";

const TIER_TABS: Array<{ value: TierFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

/**
 * Teacher Review landing screen (ADR-040): a paginated, confidence-tier
 * filterable list of `AnswerEvaluation` rows, plus a small form to manually
 * trigger evaluation for one (exam session x extracted question) pair. The
 * list endpoint has no server-side tier filter, so the tab control filters
 * the already-fetched page client-side — same convention as Module 04's
 * Question Bank Dashboard.
 */
export function EvaluationReviewDashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("answer_evaluations:create");

  const list = usePaginatedList<AnswerEvaluation>({
    queryKey: "answer-evaluations",
    fetcher: (params) => listAnswerEvaluations(params),
  });

  const [tierFilter, setTierFilter] = useState<TierFilter>("all");
  const [examSessionId, setExamSessionId] = useState("");
  const [extractedQuestionId, setExtractedQuestionId] = useState("");

  const filteredItems =
    tierFilter === "all" ? list.items : list.items.filter((row) => row.confidence_tier === tierFilter);

  const triggerMutation = useMutation({
    mutationFn: () =>
      triggerAnswerEvaluation({
        exam_session_id: examSessionId,
        extracted_question_id: extractedQuestionId,
      }),
    onSuccess: () => {
      toast("Answer evaluation triggered.", "success");
      setExamSessionId("");
      setExtractedQuestionId("");
      void queryClient.invalidateQueries({ queryKey: ["answer-evaluations"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function handleTriggerSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!examSessionId.trim() || !extractedQuestionId.trim()) {
      toast("Enter both an Exam Session ID and an Extracted Question ID.", "error");
      return;
    }
    triggerMutation.mutate();
  }

  const columns: Column<AnswerEvaluation>[] = [
    { key: "exam_session_id", header: "Exam Session", render: (row) => row.exam_session_id },
    {
      key: "confidence_tier",
      header: "Confidence",
      render: (row) =>
        row.confidence_tier ? (
          <Badge variant={statusVariant(row.confidence_tier)}>{row.confidence_tier}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "marks",
      header: "Suggested / Max Marks",
      render: (row) => `${row.suggested_marks ?? "—"} / ${row.max_marks}`,
    },
    {
      key: "review_status",
      header: "Review Status",
      render: (row) => (
        <Badge variant={statusVariant(row.review_status)}>{formatStatusLabel(row.review_status)}</Badge>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Evaluation Review Dashboard"
        description="Review AI-generated answer evaluations awaiting teacher confirmation or override."
      />

      {canCreate && (
        <Card>
          <CardHeader>
            <CardTitle>Trigger Evaluation</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleTriggerSubmit} className="flex flex-wrap items-end gap-3">
              <div className="w-64">
                <FormField htmlFor="trigger-exam-session-id" label="Exam Session ID" required>
                  <Input
                    id="trigger-exam-session-id"
                    required
                    value={examSessionId}
                    onChange={(event) => setExamSessionId(event.target.value)}
                    placeholder="Exam session UUID"
                  />
                </FormField>
              </div>
              <div className="w-64">
                <FormField htmlFor="trigger-extracted-question-id" label="Extracted Question ID" required>
                  <Input
                    id="trigger-extracted-question-id"
                    required
                    value={extractedQuestionId}
                    onChange={(event) => setExtractedQuestionId(event.target.value)}
                    placeholder="Extracted question UUID"
                  />
                </FormField>
              </div>
              <Button type="submit" disabled={triggerMutation.isPending}>
                {triggerMutation.isPending ? "Triggering..." : "Trigger Evaluation"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {TIER_TABS.map((tab) => (
          <Button
            key={tab.value}
            type="button"
            variant={tierFilter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => setTierFilter(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      <DataTable
        columns={columns}
        rows={filteredItems}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No answer evaluations found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`View evaluation ${row.id}`}
              onClick={() => navigate(`/dashboard/answer-evaluations/${row.id}`)}
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
