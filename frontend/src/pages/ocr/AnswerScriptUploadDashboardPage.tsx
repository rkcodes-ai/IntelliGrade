import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { Ban, Eye, RotateCcw, Trash2, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  bulkUploadAnswerScripts,
  cancelAnswerScript,
  listAnswerScripts,
  removeAnswerScript,
  retryAnswerScript,
  uploadAnswerScript,
} from "@/api/answerScripts";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { AnswerScript, AnswerScriptStatus } from "@/types/ocr";

const ACCEPTED_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp";

/** Statuses from which nothing further can happen without an explicit retry. */
const TERMINAL_STATUSES: AnswerScriptStatus[] = [
  "completed",
  "failed",
  "failed_validation",
  "ocr_failed",
  "cancelled",
];
const RETRYABLE_STATUSES: AnswerScriptStatus[] = ["failed", "failed_validation", "ocr_failed", "cancelled"];

function formatSize(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/**
 * Landing screen for Module 05: drag-and-drop (or click-to-browse) upload of
 * one or many answer scripts against an exam session, plus the paginated
 * list of previously uploaded scripts with per-row retry/cancel/delete.
 */
export function AnswerScriptUploadDashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canRetry = permissions.includes("answer_scripts:retry");
  const canCancel = permissions.includes("answer_scripts:cancel");
  const canDelete = permissions.includes("answer_scripts:delete");

  const list = usePaginatedList<AnswerScript>({
    queryKey: "answer-scripts",
    fetcher: (params) => listAnswerScripts(params),
  });

  const [examSessionId, setExamSessionId] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [deleting, setDeleting] = useState<AnswerScript | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["answer-scripts"] });
  }

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAnswerScript(examSessionId, file),
    onSuccess: () => {
      toast("Answer script uploaded.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const bulkUploadMutation = useMutation({
    mutationFn: (files: File[]) => bulkUploadAnswerScripts(examSessionId, files),
    onSuccess: (result) => {
      toast(
        `${result.created} uploaded, ${result.errors.length} failed.`,
        result.errors.length > 0 ? "error" : "success",
      );
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryAnswerScript(id),
    onSuccess: () => {
      toast("Answer script queued for retry.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelAnswerScript(id),
    onSuccess: () => {
      toast("Answer script cancelled.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => removeAnswerScript(id),
    onSuccess: () => {
      toast("Answer script deleted.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function handleFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) return;
    if (!examSessionId.trim()) {
      toast("Enter an Exam Session ID before uploading.", "error");
      return;
    }
    const fileArray = Array.from(files);
    if (fileArray.length === 1) {
      uploadMutation.mutate(fileArray[0]);
    } else {
      bulkUploadMutation.mutate(fileArray);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleFiles(event.dataTransfer.files);
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFiles(event.target.files);
    event.target.value = "";
  }

  const columns: Column<AnswerScript>[] = [
    { key: "filename", header: "Filename", render: (row) => row.original_filename },
    {
      key: "status",
      header: "Status",
      render: (row) => <Badge variant={statusVariant(row.status)}>{formatStatusLabel(row.status)}</Badge>,
    },
    { key: "pages", header: "Pages", render: (row) => row.page_count ?? "—" },
    { key: "size", header: "Size", render: (row) => formatSize(row.file_size_bytes) },
    { key: "uploaded", header: "Uploaded", render: (row) => new Date(row.created_at).toLocaleDateString() },
  ];

  return (
    <div>
      <PageHeader
        title="Answer Script Upload"
        description="Upload student answer scripts and track their processing status."
      />

      <div className="mb-6 flex flex-col gap-3">
        <div className="max-w-sm">
          <FormField htmlFor="exam-session-id" label="Exam Session ID" required>
            <Input
              id="exam-session-id"
              required
              value={examSessionId}
              onChange={(event) => setExamSessionId(event.target.value)}
              placeholder="Exam session UUID"
            />
          </FormField>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-label="Drag & drop files here or click to browse"
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") fileInputRef.current?.click();
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragging(false);
          }}
          onDrop={handleDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
            isDragging ? "border-primary bg-secondary" : "border-border"
          }`}
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Drag & drop files here or click to browse</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS}
            aria-label="Upload files"
            className="hidden"
            onChange={handleFileInputChange}
          />
        </div>
      </div>

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search answer scripts..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No answer scripts found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`View ${row.original_filename}`}
              onClick={() => navigate(`/dashboard/answer-scripts/${row.id}`)}
            >
              <Eye className="h-4 w-4" />
            </Button>
            {canRetry && RETRYABLE_STATUSES.includes(row.status) && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Retry ${row.original_filename}`}
                onClick={() => retryMutation.mutate(row.id)}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            )}
            {canCancel && !TERMINAL_STATUSES.includes(row.status) && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Cancel ${row.original_filename}`}
                onClick={() => cancelMutation.mutate(row.id)}
              >
                <Ban className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${row.original_filename}`}
                onClick={() => setDeleting(row)}
              >
                <Trash2 className="h-4 w-4" />
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
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete answer script?"
        description={`"${deleting?.original_filename}" will be permanently removed from the processing pipeline.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
