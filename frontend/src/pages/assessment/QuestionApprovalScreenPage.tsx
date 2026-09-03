import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";

import { approveQuestion, questionsApi, rejectQuestion } from "@/api/questions";
import { listQuestionApprovals } from "@/api/questionApprovals";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { useAppSelector } from "@/store";
import type { ApprovalDecision, Question, QuestionApproval } from "@/types/assessment";

function truncate(text: string, length = 60) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

const decisionClassName: Record<ApprovalDecision, string> = {
  approved: "text-primary",
  rejected: "text-destructive",
};

/**
 * Top-level "pending approvals inbox" — not scoped to a single question route
 * param. Pending items come from the same `questionsApi.list` used by the
 * Question Bank Dashboard, filtered client-side to `pending_review` since
 * there's no server-side filter param for this; history is the read-only
 * `QuestionApproval` audit trail.
 */
export function QuestionApprovalScreenPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canApprove = permissions.includes("questions:approve");
  const canReject = permissions.includes("questions:reject");

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const pendingList = usePaginatedList<Question>({
    queryKey: "questions",
    fetcher: (params) => questionsApi.list({ ...params, page_size: 200 }),
  });
  const historyList = usePaginatedList<QuestionApproval>({
    queryKey: "question-approvals",
    fetcher: (params) => listQuestionApprovals(params),
  });

  const pendingQuestions = pendingList.items.filter((q) => q.approval_status === "pending_review");

  const [rejecting, setRejecting] = useState<Question | null>(null);
  const [reason, setReason] = useState("");

  function invalidatePending() {
    return queryClient.invalidateQueries({ queryKey: ["questions"] });
  }

  const approveMutation = useMutation({
    mutationFn: (id: string) => approveQuestion(id),
    onSuccess: () => {
      toast("Question approved.", "success");
      void invalidatePending();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectQuestion(id, { reason }),
    onSuccess: () => {
      toast("Question rejected.", "success");
      void invalidatePending();
      setRejecting(null);
      setReason("");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openReject(question: Question) {
    setRejecting(question);
    setReason("");
  }

  function handleRejectSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!rejecting) return;
    rejectMutation.mutate({ id: rejecting.id, reason });
  }

  const pendingColumns: Column<Question>[] = [
    { key: "question_text", header: "Question Text", render: (row) => truncate(row.question_text) },
    { key: "marks", header: "Marks", render: (row) => row.marks },
    { key: "version", header: "Version", render: (row) => `v${row.current_version}` },
    {
      key: "submitted",
      header: "Submitted",
      render: () => <span className="text-warning">Pending Review</span>,
    },
  ];

  const historyColumns: Column<QuestionApproval>[] = [
    { key: "question_id", header: "Question ID", render: (row) => row.question_id },
    {
      key: "decision",
      header: "Decision",
      render: (row) => <span className={decisionClassName[row.decision]}>{row.decision}</span>,
    },
    { key: "reviewed_at", header: "Reviewed At", render: (row) => row.reviewed_at },
    { key: "comments", header: "Comments", render: (row) => row.comments ?? "—" },
  ];

  return (
    <div>
      <PageHeader
        title="Question Approvals"
        description="Review questions pending approval and browse the approval history."
      />

      <h2 className="mb-2 text-lg font-semibold tracking-tight">Pending Review</h2>
      <div className="mb-4">
        <SearchInput value={pendingList.search} onChange={pendingList.setSearch} placeholder="Search questions..." />
      </div>
      <DataTable
        columns={pendingColumns}
        rows={pendingQuestions}
        getRowId={(row) => row.id}
        isLoading={pendingList.isLoading}
        isError={pendingList.isError}
        emptyMessage="No questions pending approval."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canApprove && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Approve ${truncate(row.question_text, 30)}`}
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate(row.id)}
              >
                <Check className="h-4 w-4" />
              </Button>
            )}
            {canReject && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Reject ${truncate(row.question_text, 30)}`}
                onClick={() => openReject(row)}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      />

      <h2 className="mb-2 mt-8 text-lg font-semibold tracking-tight">Approval History</h2>
      <div className="mb-4">
        <SearchInput
          value={historyList.search}
          onChange={historyList.setSearch}
          placeholder="Search approval history..."
        />
      </div>
      <DataTable
        columns={historyColumns}
        rows={historyList.items}
        getRowId={(row) => row.id}
        isLoading={historyList.isLoading}
        isError={historyList.isError}
        emptyMessage="No approval history found."
      />
      <PaginationControls
        page={historyList.page}
        pageSize={historyList.pageSize}
        total={historyList.total}
        totalPages={historyList.totalPages}
        onPageChange={historyList.setPage}
        onPageSizeChange={historyList.setPageSize}
      />

      <FormDialog
        open={rejecting !== null}
        onOpenChange={(open) => !open && setRejecting(null)}
        title="Reject question?"
        description={rejecting ? `"${truncate(rejecting.question_text, 80)}"` : undefined}
        onSubmit={handleRejectSubmit}
        isSubmitting={rejectMutation.isPending}
        submitLabel="Reject"
      >
        <FormField htmlFor="reject-reason" label="Reason" required>
          <Textarea
            id="reject-reason"
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
