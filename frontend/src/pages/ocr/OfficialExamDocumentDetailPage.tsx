import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileEdit, RotateCcw, Trash2, XCircle } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import {
  cancelOfficialExamDocument,
  downloadOfficialExamDocument,
  getOfficialExamDocument,
  removeOfficialExamDocument,
  retryOfficialExamDocument,
} from "@/api/officialExamDocuments";
import { DetailLoading, DetailNotFound } from "@/components/common/DetailState";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/context/ToastProvider";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type {
  OfficialExamDocumentOCRStatus,
  OfficialExamDocumentType,
} from "@/types/officialExam";

const RETRYABLE_STATUSES: OfficialExamDocumentOCRStatus[] = ["failed", "cancelled"];
const TERMINAL_STATUSES: OfficialExamDocumentOCRStatus[] = ["completed", "failed", "cancelled"];

const VERIFICATION_ROUTE_BY_TYPE: Record<OfficialExamDocumentType, string> = {
  question_paper: "questions",
  model_answer: "model-answers",
  mark_scheme: "mark-scheme",
};

const VERIFICATION_LABEL_BY_TYPE: Record<OfficialExamDocumentType, string> = {
  question_paper: "Verify Extracted Questions",
  model_answer: "Verify Extracted Model Answers",
  mark_scheme: "Verify Mark Scheme Ranges",
};

function formatFileSize(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/**
 * Read-only detail view of one `OfficialExamDocument` — the landing point
 * navigated to from `OfficialDocumentUploadDashboardPage`'s row actions.
 * Its main job is routing a teacher into the document-type-specific
 * verification screen (Question/Model Answer/Mark Scheme Verification)
 * once ingestion has completed.
 */
export function OfficialExamDocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canRead = permissions.includes("official_exam_documents:read");
  const canRetry = permissions.includes("official_exam_documents:retry");
  const canCancel = permissions.includes("official_exam_documents:cancel");
  const canDelete = permissions.includes("official_exam_documents:delete");

  const {
    data: document,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["official-exam-documents", id],
    queryFn: () => getOfficialExamDocument(id!),
    enabled: Boolean(id),
  });

  function invalidateDocument() {
    return queryClient.invalidateQueries({ queryKey: ["official-exam-documents", id] });
  }

  const downloadMutation = useMutation({
    mutationFn: () => downloadOfficialExamDocument(id!),
    onSuccess: (result) => window.open(result.url, "_blank"),
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const retryMutation = useMutation({
    mutationFn: () => retryOfficialExamDocument(id!),
    onSuccess: () => {
      toast("Document queued for retry.", "success");
      void invalidateDocument();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelOfficialExamDocument(id!),
    onSuccess: () => {
      toast("Document cancelled.", "success");
      void invalidateDocument();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const removeMutation = useMutation({
    mutationFn: () => removeOfficialExamDocument(id!),
    onSuccess: () => {
      toast("Document deleted.", "success");
      navigate("/dashboard/official-exam-documents");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  if (isLoading) {
    return <DetailLoading />;
  }

  if (isError || !document) {
    return <DetailNotFound message="Document not found." />;
  }

  const canShowRetry = canRetry && RETRYABLE_STATUSES.includes(document.ocr_status);
  const canShowCancel = canCancel && !TERMINAL_STATUSES.includes(document.ocr_status);
  const verificationPath = VERIFICATION_ROUTE_BY_TYPE[document.document_type];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Official Exam Document Detail"
        description="Read-only detail view of an uploaded official exam document."
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
            {document.ocr_status === "completed" && (
              <Button
                onClick={() =>
                  navigate(`/dashboard/official-exam-documents/${id}/${verificationPath}`)
                }
              >
                <FileEdit className="h-4 w-4" />
                {VERIFICATION_LABEL_BY_TYPE[document.document_type]}
              </Button>
            )}
            {canShowRetry && (
              <Button
                variant="outline"
                onClick={() => retryMutation.mutate()}
                disabled={retryMutation.isPending}
              >
                <RotateCcw className="h-4 w-4" />
                Retry
              </Button>
            )}
            {canShowCancel && (
              <Button
                variant="outline"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
              >
                <XCircle className="h-4 w-4" />
                Cancel
              </Button>
            )}
            {canDelete && (
              <Button
                variant="destructive"
                aria-label={`Delete ${document.original_filename}`}
                onClick={() => removeMutation.mutate()}
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
            <CardTitle>{document.original_filename}</CardTitle>
            <Badge variant={statusVariant(document.ocr_status)} className="h-fit shrink-0">
              {formatStatusLabel(document.ocr_status)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {document.failure_reason && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {document.failure_reason}
            </div>
          )}
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Document Type
              </dt>
              <dd className="mt-0.5 text-sm">{formatStatusLabel(document.document_type)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Verification Status
              </dt>
              <dd className="mt-0.5">
                <Badge variant={statusVariant(document.verification_status)}>
                  {formatStatusLabel(document.verification_status)}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Mime Type
              </dt>
              <dd className="mt-0.5 text-sm">{document.mime_type}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Page Count
              </dt>
              <dd className="mt-0.5 text-sm">{document.page_count ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                File Size
              </dt>
              <dd className="mt-0.5 text-sm">{formatFileSize(document.file_size_bytes)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Checksum
              </dt>
              <dd className="mt-0.5 text-sm">
                {document.checksum_sha256 ? (
                  <span className="font-mono">{document.checksum_sha256.slice(0, 16)}…</span>
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
