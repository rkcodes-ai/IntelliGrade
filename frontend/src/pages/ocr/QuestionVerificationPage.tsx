import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Pencil, Sparkles } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { listExtractedQuestions, updateExtractedQuestion, verifyExtractedQuestion } from "@/api/extractedQuestions";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { VerificationStepNav } from "@/components/common/VerificationStepNav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { ExtractedQuestion } from "@/types/officialExam";

function truncate(text: string, length = 80) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

interface QuestionFormState {
  question_text: string;
  final_marks: string;
}

/**
 * Stage: Teacher Verification screen for one `OfficialExamDocument`'s
 * extracted questions — server-side filtered to `documentId` from the route,
 * mirroring `ProcessingHistoryPage.tsx`'s filtered-by-parent-id pattern. Rows
 * are written internally by the ingestion pipeline (see
 * `api/extractedQuestions.ts`); teachers only edit/verify an already-extracted
 * row via a per-row `FormDialog`, never create/delete one here.
 */
export function QuestionVerificationPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canUpdate = permissions.includes("extracted_questions:update");
  const canVerify = permissions.includes("extracted_questions:verify");
  const canReviewAIReference = permissions.includes("ai_reference_answers:read");

  const list = usePaginatedList<ExtractedQuestion>({
    queryKey: "extracted-questions",
    fetcher: (params) => listExtractedQuestions({ ...params, document_id: documentId }),
  });

  const [editing, setEditing] = useState<ExtractedQuestion | null>(null);
  const [form, setForm] = useState<QuestionFormState>({ question_text: "", final_marks: "" });

  function invalidateList() {
    return queryClient.invalidateQueries({ queryKey: ["extracted-questions"] });
  }

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { question_text: string; final_marks: number | null } }) =>
      updateExtractedQuestion(id, data),
    onSuccess: () => {
      toast("Question updated.", "success");
      void invalidateList();
      setEditing(null);
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyExtractedQuestion(id),
    onSuccess: () => {
      toast("Question verified.", "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openEdit(question: ExtractedQuestion) {
    setEditing(question);
    setForm({
      question_text: question.question_text,
      final_marks: question.final_marks ?? "",
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    updateMutation.mutate({
      id: editing.id,
      data: {
        question_text: form.question_text,
        final_marks: form.final_marks === "" ? null : Number(form.final_marks),
      },
    });
  }

  const columns: Column<ExtractedQuestion>[] = [
    { key: "question_number", header: "Q#", render: (row) => row.question_number },
    { key: "question_text", header: "Question Text", render: (row) => truncate(row.question_text) },
    {
      key: "detected_marks",
      header: "OCR-detected Marks",
      render: (row) => row.detected_marks ?? "—",
    },
    { key: "final_marks", header: "Final Marks", render: (row) => row.final_marks ?? "—" },
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
        title="Question Verification"
        description="Verify and correct OCR-extracted questions for this document."
        actions={
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
            Back to document
          </Button>
        }
      />

      {documentId && <VerificationStepNav documentId={documentId} current="questions" />}

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No extracted questions found for this document."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit question ${row.question_number}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canVerify && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Verify question ${row.question_number}`}
                disabled={row.verification_status === "verified" || verifyMutation.isPending}
                onClick={() => verifyMutation.mutate(row.id)}
              >
                <Check className="h-4 w-4" />
              </Button>
            )}
            {canReviewAIReference && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Review AI reference answer for question ${row.question_number}`}
                onClick={() => navigate(`/dashboard/extracted-questions/${row.id}/ai-reference-answer`)}
              >
                <Sparkles className="h-4 w-4" />
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
        title={`Edit Question ${editing?.question_number ?? ""}`}
        onSubmit={handleSubmit}
        isSubmitting={updateMutation.isPending}
        submitLabel="Save"
      >
        <FormField htmlFor="question-text" label="Question Text" required>
          <Textarea
            id="question-text"
            required
            value={form.question_text}
            onChange={(event) => setForm({ ...form, question_text: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="question-final-marks" label="Final Marks">
          <Input
            id="question-final-marks"
            type="number"
            step="any"
            min="0"
            value={form.final_marks}
            onChange={(event) => setForm({ ...form, final_marks: event.target.value })}
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
