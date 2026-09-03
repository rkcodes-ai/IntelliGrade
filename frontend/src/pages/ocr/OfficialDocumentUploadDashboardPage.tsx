import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { Ban, Eye, RotateCcw, Trash2, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  cancelOfficialExamDocument,
  listOfficialExamDocuments,
  removeOfficialExamDocument,
  retryOfficialExamDocument,
  uploadOfficialExamDocument,
} from "@/api/officialExamDocuments";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type {
  OfficialExamDocument,
  OfficialExamDocumentOCRStatus,
  OfficialExamDocumentType,
} from "@/types/officialExam";

const ACCEPTED_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp";

const DOCUMENT_TYPE_OPTIONS: { value: OfficialExamDocumentType; label: string }[] = [
  { value: "question_paper", label: "Question Paper" },
  { value: "model_answer", label: "Model Answer" },
  { value: "mark_scheme", label: "Mark Scheme" },
];

/** Statuses from which nothing further can happen without an explicit retry. */
const TERMINAL_STATUSES: OfficialExamDocumentOCRStatus[] = ["completed", "failed", "cancelled"];
const RETRYABLE_STATUSES: OfficialExamDocumentOCRStatus[] = ["failed", "cancelled"];

/**
 * Module 06 landing screen: single-file drag-and-drop (or click-to-browse)
 * upload of one official exam document (question paper / model answer /
 * mark scheme) against an exam, plus the paginated list of previously
 * uploaded documents with per-row retry/cancel/delete. Unlike answer
 * scripts there is no bulk-upload endpoint for this entity, so only one
 * file is accepted per upload.
 */
export function OfficialDocumentUploadDashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canRetry = permissions.includes("official_exam_documents:retry");
  const canCancel = permissions.includes("official_exam_documents:cancel");
  const canDelete = permissions.includes("official_exam_documents:delete");

  const list = usePaginatedList<OfficialExamDocument>({
    queryKey: "official-exam-documents",
    fetcher: (params) => listOfficialExamDocuments(params),
  });

  const [examId, setExamId] = useState("");
  const [documentType, setDocumentType] = useState<OfficialExamDocumentType | "">("");
  const [isDragging, setIsDragging] = useState(false);
  const [deleting, setDeleting] = useState<OfficialExamDocument | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["official-exam-documents"] });
  }

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      uploadOfficialExamDocument(examId, documentType as OfficialExamDocumentType, file),
    onSuccess: () => {
      toast("Official exam document uploaded.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryOfficialExamDocument(id),
    onSuccess: () => {
      toast("Document queued for retry.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelOfficialExamDocument(id),
    onSuccess: () => {
      toast("Document cancelled.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => removeOfficialExamDocument(id),
    onSuccess: () => {
      toast("Document deleted.", "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function handleFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) return;
    if (!examId.trim()) {
      toast("Enter an Exam ID before uploading.", "error");
      return;
    }
    if (!documentType) {
      toast("Select a document type before uploading.", "error");
      return;
    }
    const file = Array.from(files)[0];
    uploadMutation.mutate(file);
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

  const columns: Column<OfficialExamDocument>[] = [
    { key: "filename", header: "Filename", render: (row) => row.original_filename },
    {
      key: "document_type",
      header: "Document Type",
      render: (row) => <Badge variant="outline">{formatStatusLabel(row.document_type)}</Badge>,
    },
    {
      key: "ocr_status",
      header: "OCR Status",
      render: (row) => <Badge variant={statusVariant(row.ocr_status)}>{formatStatusLabel(row.ocr_status)}</Badge>,
    },
    {
      key: "verification_status",
      header: "Verification",
      render: (row) => (
        <Badge variant={statusVariant(row.verification_status)}>
          {formatStatusLabel(row.verification_status)}
        </Badge>
      ),
    },
    { key: "uploaded", header: "Uploaded", render: (row) => new Date(row.created_at).toLocaleDateString() },
  ];

  return (
    <div>
      <PageHeader
        title="Official Document Upload"
        description="Upload official exam documents (question papers, model answers, mark schemes) and track their processing status."
      />

      <div className="mb-6 flex flex-col gap-3">
        <div className="flex flex-wrap gap-3">
          <div className="max-w-sm flex-1">
            <FormField htmlFor="exam-id" label="Exam ID" required>
              <Input
                id="exam-id"
                required
                value={examId}
                onChange={(event) => setExamId(event.target.value)}
                placeholder="Exam UUID"
              />
            </FormField>
          </div>
          <div className="max-w-sm flex-1">
            <FormField htmlFor="document-type" label="Document Type" required>
              <Select
                id="document-type"
                required
                value={documentType}
                onChange={(event) => setDocumentType(event.target.value as OfficialExamDocumentType)}
              >
                <option value="" disabled>
                  Select a document type
                </option>
                {DOCUMENT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-label="Drag & drop a file here or click to browse"
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
          <p className="text-sm text-muted-foreground">Drag & drop a file here or click to browse</p>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            aria-label="Upload file"
            className="hidden"
            onChange={handleFileInputChange}
          />
        </div>
      </div>

      <div className="mb-4">
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search official exam documents..."
        />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No official exam documents found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`View ${row.original_filename}`}
              onClick={() => navigate(`/dashboard/official-exam-documents/${row.id}`)}
            >
              <Eye className="h-4 w-4" />
            </Button>
            {canRetry && RETRYABLE_STATUSES.includes(row.ocr_status) && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Retry ${row.original_filename}`}
                onClick={() => retryMutation.mutate(row.id)}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            )}
            {canCancel && !TERMINAL_STATUSES.includes(row.ocr_status) && (
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
        title="Delete official exam document?"
        description={`"${deleting?.original_filename}" will be permanently removed from the processing pipeline.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
