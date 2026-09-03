import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  approveExamResult,
  bulkApproveExamResults,
  bulkLockExamResults,
  bulkPublishExamResults,
  finalizeBatchResults,
  finalizeExamResults,
  finalizeStudentResult,
  listExamResults,
  lockExamResult,
  publishExamResult,
  unlockExamResult,
} from "@/api/examResults";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
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
import type { BulkActionResult, ExamResult } from "@/types/teacherReview";

const QUERY_KEY = "exam-results";

function bulkResultMessage(result: BulkActionResult): string {
  return `${result.succeeded_count} finalized, ${result.failed.length} failed`;
}

/**
 * Feature 4/5 (ADR-042) screen: finalize student/exam/batch results, then
 * approve -> lock -> publish (or unlock) each `ExamResult` through its
 * validated state machine. Row actions are gated on both the row's current
 * `status` and the caller's permissions; unlock is wrapped in a
 * `ConfirmDialog` since it reopens a finalized result for further edits.
 */
export function ResultFinalizationPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);

  const canFinalize = permissions.includes("exam_results:finalize");
  const canApprove = permissions.includes("exam_results:approve");
  const canLock = permissions.includes("exam_results:lock");
  const canPublish = permissions.includes("exam_results:publish");
  const canUnlock = permissions.includes("exam_results:unlock");
  const canBulk = canApprove || canLock || canPublish;

  const list = usePaginatedList<ExamResult>({
    queryKey: QUERY_KEY,
    fetcher: (params) => listExamResults(params),
  });

  const [studentExamSessionId, setStudentExamSessionId] = useState("");
  const [examId, setExamId] = useState("");
  const [batchExamId, setBatchExamId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [bulkExamId, setBulkExamId] = useState("");
  const [unlockTarget, setUnlockTarget] = useState<ExamResult | null>(null);

  function invalidateList() {
    return queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
  }

  const finalizeStudentMutation = useMutation({
    mutationFn: () => finalizeStudentResult({ exam_session_id: studentExamSessionId.trim() }),
    onSuccess: () => {
      toast("Student result finalized.", "success");
      setStudentExamSessionId("");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const finalizeExamMutation = useMutation({
    mutationFn: () => finalizeExamResults({ exam_id: examId.trim() }),
    onSuccess: (result) => {
      toast(bulkResultMessage(result), "success");
      setExamId("");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const finalizeBatchMutation = useMutation({
    mutationFn: () => finalizeBatchResults({ exam_id: batchExamId.trim(), batch_id: batchId.trim() }),
    onSuccess: (result) => {
      toast(bulkResultMessage(result), "success");
      setBatchExamId("");
      setBatchId("");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const bulkApproveMutation = useMutation({
    mutationFn: () => bulkApproveExamResults({ exam_id: bulkExamId.trim() }),
    onSuccess: (result) => {
      toast(bulkResultMessage(result), "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const bulkLockMutation = useMutation({
    mutationFn: () => bulkLockExamResults({ exam_id: bulkExamId.trim() }),
    onSuccess: (result) => {
      toast(bulkResultMessage(result), "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const bulkPublishMutation = useMutation({
    mutationFn: () => bulkPublishExamResults({ exam_id: bulkExamId.trim() }),
    onSuccess: (result) => {
      toast(bulkResultMessage(result), "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => approveExamResult(id),
    onSuccess: () => {
      toast("Result approved.", "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const lockMutation = useMutation({
    mutationFn: (id: string) => lockExamResult(id),
    onSuccess: () => {
      toast("Result locked.", "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => publishExamResult(id),
    onSuccess: () => {
      toast("Result published.", "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const unlockMutation = useMutation({
    mutationFn: (id: string) => unlockExamResult(id),
    onSuccess: () => {
      toast("Result unlocked.", "success");
      setUnlockTarget(null);
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function handleFinalizeStudentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!studentExamSessionId.trim()) return;
    finalizeStudentMutation.mutate();
  }

  function handleFinalizeExamSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!examId.trim()) return;
    finalizeExamMutation.mutate();
  }

  function handleFinalizeBatchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!batchExamId.trim() || !batchId.trim()) return;
    finalizeBatchMutation.mutate();
  }

  const columns: Column<ExamResult>[] = [
    { key: "exam_session_id", header: "Exam Session ID", render: (row) => row.exam_session_id },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <Badge variant={statusVariant(row.status)}>{formatStatusLabel(row.status)}</Badge>
      ),
    },
    {
      key: "marks",
      header: "Total Marks",
      render: (row) => `${row.total_marks ?? "—"} / ${row.total_max_marks ?? "—"}`,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Result Finalization & Locking"
        description="Finalize AI-suggested marks into official exam results, then approve, lock, and publish them."
      />

      {canFinalize && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Finalize Student</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleFinalizeStudentSubmit} className="flex flex-col gap-3">
                <FormField htmlFor="finalize-student-exam-session-id" label="Exam Session ID" required>
                  <Input
                    id="finalize-student-exam-session-id"
                    required
                    value={studentExamSessionId}
                    onChange={(event) => setStudentExamSessionId(event.target.value)}
                    placeholder="Exam session UUID"
                  />
                </FormField>
                <Button type="submit" disabled={finalizeStudentMutation.isPending}>
                  {finalizeStudentMutation.isPending ? "Finalizing..." : "Finalize Student"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Finalize Exam</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleFinalizeExamSubmit} className="flex flex-col gap-3">
                <FormField htmlFor="finalize-exam-id" label="Exam ID" required>
                  <Input
                    id="finalize-exam-id"
                    required
                    value={examId}
                    onChange={(event) => setExamId(event.target.value)}
                    placeholder="Exam UUID"
                  />
                </FormField>
                <Button type="submit" disabled={finalizeExamMutation.isPending}>
                  {finalizeExamMutation.isPending ? "Finalizing..." : "Finalize Exam"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Finalize Batch</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleFinalizeBatchSubmit} className="flex flex-col gap-3">
                <FormField htmlFor="finalize-batch-exam-id" label="Exam ID" required>
                  <Input
                    id="finalize-batch-exam-id"
                    required
                    value={batchExamId}
                    onChange={(event) => setBatchExamId(event.target.value)}
                    placeholder="Exam UUID"
                  />
                </FormField>
                <FormField htmlFor="finalize-batch-id" label="Batch ID" required>
                  <Input
                    id="finalize-batch-id"
                    required
                    value={batchId}
                    onChange={(event) => setBatchId(event.target.value)}
                    placeholder="Batch UUID"
                  />
                </FormField>
                <Button type="submit" disabled={finalizeBatchMutation.isPending}>
                  {finalizeBatchMutation.isPending ? "Finalizing..." : "Finalize Batch"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {canBulk && (
        <Card>
          <CardHeader>
            <CardTitle>Bulk Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-64">
                <FormField htmlFor="bulk-exam-id" label="Exam ID">
                  <Input
                    id="bulk-exam-id"
                    value={bulkExamId}
                    onChange={(event) => setBulkExamId(event.target.value)}
                    placeholder="Exam UUID"
                  />
                </FormField>
              </div>
              {canApprove && (
                <Button
                  variant="outline"
                  disabled={!bulkExamId.trim() || bulkApproveMutation.isPending}
                  onClick={() => bulkApproveMutation.mutate()}
                >
                  {bulkApproveMutation.isPending ? "Approving..." : "Bulk Approve"}
                </Button>
              )}
              {canLock && (
                <Button
                  variant="outline"
                  disabled={!bulkExamId.trim() || bulkLockMutation.isPending}
                  onClick={() => bulkLockMutation.mutate()}
                >
                  {bulkLockMutation.isPending ? "Locking..." : "Bulk Lock"}
                </Button>
              )}
              {canPublish && (
                <Button
                  variant="outline"
                  disabled={!bulkExamId.trim() || bulkPublishMutation.isPending}
                  onClick={() => bulkPublishMutation.mutate()}
                >
                  {bulkPublishMutation.isPending ? "Publishing..." : "Bulk Publish"}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No exam results found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {row.status === "under_review" && canApprove && (
              <Button
                size="sm"
                variant="outline"
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate(row.id)}
              >
                Approve
              </Button>
            )}
            {row.status === "approved" && canLock && (
              <Button
                size="sm"
                variant="outline"
                disabled={lockMutation.isPending}
                onClick={() => lockMutation.mutate(row.id)}
              >
                Lock
              </Button>
            )}
            {row.status === "locked" && canPublish && (
              <Button
                size="sm"
                variant="outline"
                disabled={publishMutation.isPending}
                onClick={() => publishMutation.mutate(row.id)}
              >
                Publish
              </Button>
            )}
            {(row.status === "locked" || row.status === "published") && canUnlock && (
              <Button size="sm" variant="outline" onClick={() => setUnlockTarget(row)}>
                Unlock
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

      <ConfirmDialog
        open={unlockTarget != null}
        onOpenChange={(open) => {
          if (!open) setUnlockTarget(null);
        }}
        title="Unlock this result?"
        description="Unlock this result? Further edits will be allowed again."
        confirmLabel="Unlock"
        isConfirming={unlockMutation.isPending}
        onConfirm={() => {
          if (unlockTarget) unlockMutation.mutate(unlockTarget.id);
        }}
      />
    </div>
  );
}
