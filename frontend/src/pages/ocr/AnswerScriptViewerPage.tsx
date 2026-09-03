import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, History, RotateCcw, Trash2, XCircle } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import {
  cancelAnswerScript,
  downloadAnswerScript,
  getAnswerScript,
  removeAnswerScript,
  retryAnswerScript,
} from "@/api/answerScripts";
import { listAnswerScriptPages } from "@/api/answerScriptPages";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { useAppSelector } from "@/store";
import type { AnswerScriptPage, AnswerScriptPageStatus, AnswerScriptStatus } from "@/types/ocr";

const RETRYABLE_STATUSES: AnswerScriptStatus[] = ["failed", "failed_validation", "ocr_failed", "cancelled"];
const TERMINAL_STATUSES: AnswerScriptStatus[] = [
  "completed",
  "failed",
  "failed_validation",
  "ocr_failed",
  "cancelled",
];

function statusBadgeClassName(status: AnswerScriptStatus): string {
  if (status === "completed" || status === "ocr_complete") return "text-primary";
  if (status === "failed" || status === "cancelled" || status.endsWith("_failed")) return "text-destructive";
  return "text-warning";
}

function pageStatusBadgeClassName(status: AnswerScriptPageStatus): string {
  if (status === "ocr_complete") return "text-primary";
  if (status === "ocr_failed") return "text-destructive";
  return "text-warning";
}

function formatFileSize(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function summarizeStructuredContent(content: Record<string, unknown> | null): string | null {
  if (!content) return null;
  const pageCount = typeof content.page_count === "number" ? content.page_count : "—";
  const pages = Array.isArray(content.pages) ? (content.pages as Record<string, unknown>[]) : [];
  const questionCount = pages.reduce((total, page) => {
    const detected = page.detected_questions;
    return total + (Array.isArray(detected) ? detected.length : 0);
  }, 0);
  return `${pageCount} page(s) processed, ${questionCount} detected question marker(s)`;
}

function MetadataItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}

/**
 * Read-only detail view of a single `AnswerScript`, mirroring
 * `QuestionViewerPage.tsx`'s single-entity-fetch-via-useParams pattern. Pages
 * sub-table and workflow actions (download/retry/cancel/delete) live here
 * since there's no separate editor screen for this pipeline-managed entity.
 */
export function AnswerScriptViewerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canRead = permissions.includes("answer_scripts:read");
  const canRetry = permissions.includes("answer_scripts:retry");
  const canCancel = permissions.includes("answer_scripts:cancel");
  const canDelete = permissions.includes("answer_scripts:delete");

  const [deleteOpen, setDeleteOpen] = useState(false);

  const {
    data: answerScript,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["answer-scripts", id],
    queryFn: () => getAnswerScript(id!),
    enabled: Boolean(id),
  });

  const pagesList = usePaginatedList<AnswerScriptPage>({
    queryKey: "answer-script-pages",
    fetcher: (params) => listAnswerScriptPages({ ...params, answer_script_id: id, page_size: 200 }),
  });

  function invalidateAnswerScript() {
    return queryClient.invalidateQueries({ queryKey: ["answer-scripts", id] });
  }

  const downloadMutation = useMutation({
    mutationFn: () => downloadAnswerScript(id!),
    onSuccess: (result) => window.open(result.url, "_blank"),
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const retryMutation = useMutation({
    mutationFn: () => retryAnswerScript(id!),
    onSuccess: () => {
      toast("Answer script queued for retry.", "success");
      void invalidateAnswerScript();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelAnswerScript(id!),
    onSuccess: () => {
      toast("Answer script cancelled.", "success");
      void invalidateAnswerScript();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const removeMutation = useMutation({
    mutationFn: () => removeAnswerScript(id!),
    onSuccess: () => {
      toast("Answer script deleted.", "success");
      navigate("/dashboard/answer-scripts");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <Spinner />
      </div>
    );
  }

  if (isError || !answerScript) {
    return <p className="p-6 text-sm text-muted-foreground">Answer script not found.</p>;
  }

  const canShowRetry = canRetry && RETRYABLE_STATUSES.includes(answerScript.status);
  const canShowCancel = canCancel && !TERMINAL_STATUSES.includes(answerScript.status);
  const structuredSummary = summarizeStructuredContent(answerScript.structured_content);

  const pageColumns: Column<AnswerScriptPage>[] = [
    { key: "page_number", header: "Page #", render: (row) => row.page_number },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <span className={pageStatusBadgeClassName(row.status)}>{row.status.replace(/_/g, " ")}</span>
      ),
    },
    { key: "is_blank", header: "Blank", render: (row) => (row.is_blank ? "Yes" : "No") },
    {
      key: "dimensions",
      header: "Dimensions",
      render: (row) => (row.width_px != null && row.height_px != null ? `${row.width_px}x${row.height_px}` : "—"),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Answer Script Detail"
        description="Read-only detail view of an uploaded answer script and its pages."
        actions={
          <>
            {canRead && (
              <Button
                variant="outline"
                onClick={() => downloadMutation.mutate()}
                disabled={downloadMutation.isPending}
              >
                <Download className="h-4 w-4" />
                Download
              </Button>
            )}
            {canShowRetry && (
              <Button variant="outline" onClick={() => retryMutation.mutate()} disabled={retryMutation.isPending}>
                <RotateCcw className="h-4 w-4" />
                Retry
              </Button>
            )}
            {canShowCancel && (
              <Button variant="outline" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
                <XCircle className="h-4 w-4" />
                Cancel
              </Button>
            )}
            <Button variant="outline" onClick={() => navigate(`/dashboard/answer-scripts/${id}/history`)}>
              <History className="h-4 w-4" />
              View Processing History
            </Button>
            {canDelete && (
              <Button
                variant="destructive"
                aria-label={`Delete ${answerScript.original_filename}`}
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            )}
          </>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <CardTitle>{answerScript.original_filename}</CardTitle>
            <span
              className={cn("h-fit shrink-0 rounded-full px-2.5 py-1 text-xs font-medium", statusBadgeClassName(answerScript.status))}
            >
              {answerScript.status.replace(/_/g, " ")}
            </span>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {answerScript.failure_reason && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {answerScript.failure_reason}
            </div>
          )}
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <MetadataItem label="Mime Type" value={answerScript.mime_type} />
            <MetadataItem label="Page Count" value={answerScript.page_count ?? "—"} />
            <MetadataItem label="File Size" value={formatFileSize(answerScript.file_size_bytes)} />
            <MetadataItem
              label="Checksum"
              value={
                answerScript.checksum_sha256 ? (
                  <span className="font-mono">{answerScript.checksum_sha256.slice(0, 16)}…</span>
                ) : (
                  "—"
                )
              }
            />
            {structuredSummary && (
              <MetadataItem label="Structured Content" value={structuredSummary} />
            )}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pages</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={pageColumns}
            rows={pagesList.items}
            getRowId={(row) => row.id}
            isLoading={pagesList.isLoading}
            isError={pagesList.isError}
            emptyMessage="No pages found."
            renderActions={(row) => (
              <div className="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`View Page ${row.page_number}`}
                  onClick={() => navigate(`/dashboard/answer-scripts/${id}/pages/${row.id}`)}
                >
                  <Eye className="h-4 w-4" />
                </Button>
              </div>
            )}
          />
        </CardContent>
      </Card>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete answer script?"
        description={`"${answerScript.original_filename}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => removeMutation.mutate(undefined, { onSuccess: () => setDeleteOpen(false) })}
      />
    </div>
  );
}
