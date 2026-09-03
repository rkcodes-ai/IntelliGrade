import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Pencil } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import {
  listExtractedModelAnswers,
  updateExtractedModelAnswer,
  verifyExtractedModelAnswer,
} from "@/api/extractedModelAnswers";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { VerificationStepNav } from "@/components/common/VerificationStepNav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { ExtractedModelAnswer } from "@/types/officialExam";

function truncate(text: string, length = 80) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

interface ModelAnswerFormState {
  answer_text: string;
}

/**
 * Stage: Teacher Verification screen for one `OfficialExamDocument`'s
 * extracted model answers — server-side filtered to `documentId` from the
 * route, identical shape to `QuestionVerificationPage.tsx` minus the marks
 * fields (model answers carry no marks of their own). Rows are written
 * internally by the ingestion pipeline (see `api/extractedModelAnswers.ts`);
 * teachers only edit/verify an already-extracted row here.
 */
export function ModelAnswerVerificationPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canUpdate = permissions.includes("extracted_model_answers:update");
  const canVerify = permissions.includes("extracted_model_answers:verify");

  const list = usePaginatedList<ExtractedModelAnswer>({
    queryKey: "extracted-model-answers",
    fetcher: (params) => listExtractedModelAnswers({ ...params, document_id: documentId }),
  });

  const [editing, setEditing] = useState<ExtractedModelAnswer | null>(null);
  const [form, setForm] = useState<ModelAnswerFormState>({ answer_text: "" });

  function invalidateList() {
    return queryClient.invalidateQueries({ queryKey: ["extracted-model-answers"] });
  }

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { answer_text: string } }) =>
      updateExtractedModelAnswer(id, data),
    onSuccess: () => {
      toast("Model answer updated.", "success");
      void invalidateList();
      setEditing(null);
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyExtractedModelAnswer(id),
    onSuccess: () => {
      toast("Model answer verified.", "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openEdit(answer: ExtractedModelAnswer) {
    setEditing(answer);
    setForm({ answer_text: answer.answer_text });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    updateMutation.mutate({ id: editing.id, data: { answer_text: form.answer_text } });
  }

  const columns: Column<ExtractedModelAnswer>[] = [
    { key: "question_number", header: "Q#", render: (row) => row.question_number },
    { key: "answer_text", header: "Answer Text", render: (row) => truncate(row.answer_text) },
    {
      key: "verification_status",
      header: "Status",
      render: (row) => (
        <Badge variant={statusVariant(row.verification_status)}>
          {formatStatusLabel(row.verification_status)}
        </Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Model Answer Verification"
        description="Verify and correct OCR-extracted model answers for this document."
        actions={
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
            Back to document
          </Button>
        }
      />

      {documentId && <VerificationStepNav documentId={documentId} current="model-answers" />}

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No extracted model answers found for this document."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit model answer ${row.question_number}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canVerify && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Verify model answer ${row.question_number}`}
                disabled={row.verification_status === "verified" || verifyMutation.isPending}
                onClick={() => verifyMutation.mutate(row.id)}
              >
                <Check className="h-4 w-4" />
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

      <FormDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={`Edit Model Answer ${editing?.question_number ?? ""}`}
        onSubmit={handleSubmit}
        isSubmitting={updateMutation.isPending}
        submitLabel="Save"
      >
        <FormField htmlFor="answer-text" label="Answer Text" required>
          <Textarea
            id="answer-text"
            required
            value={form.answer_text}
            onChange={(event) => setForm({ ...form, answer_text: event.target.value })}
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
