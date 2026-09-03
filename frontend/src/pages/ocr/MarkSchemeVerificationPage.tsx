import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Pencil, Sparkles } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import {
  expandMarkScheme,
  listMarkSchemeRanges,
  updateMarkSchemeRange,
  verifyMarkSchemeRange,
} from "@/api/markSchemeRanges";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { VerificationStepNav } from "@/components/common/VerificationStepNav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { MarkSchemeRange } from "@/types/officialExam";

interface MarkSchemeFormState {
  question_range_start: string;
  question_range_end: string;
  marks_per_question: string;
}

/**
 * Stage: Teacher Verification screen for one `OfficialExamDocument`'s
 * mark-scheme ranges — server-side filtered to `documentId` from the route,
 * same editable-row/`FormDialog` shape as `QuestionVerificationPage.tsx`.
 * Additionally hosts the "Preview Expansion" panel, which calls the live
 * `GET /mark-scheme-ranges/expand` endpoint (`expandMarkScheme`) to show the
 * data-driven per-question maximum marks — this app never hardcodes or
 * client-computes a mark range anywhere, per the module brief.
 */
export function MarkSchemeVerificationPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canUpdate = permissions.includes("mark_scheme_ranges:update");
  const canVerify = permissions.includes("mark_scheme_ranges:verify");

  const list = usePaginatedList<MarkSchemeRange>({
    queryKey: "mark-scheme-ranges",
    fetcher: (params) => listMarkSchemeRanges({ ...params, document_id: documentId }),
  });

  const [editing, setEditing] = useState<MarkSchemeRange | null>(null);
  const [form, setForm] = useState<MarkSchemeFormState>({
    question_range_start: "",
    question_range_end: "",
    marks_per_question: "",
  });

  function invalidateList() {
    return queryClient.invalidateQueries({ queryKey: ["mark-scheme-ranges"] });
  }

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { question_range_start: string; question_range_end: string; marks_per_question: number };
    }) => updateMarkSchemeRange(id, data),
    onSuccess: () => {
      toast("Mark scheme range updated.", "success");
      void invalidateList();
      setEditing(null);
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyMarkSchemeRange(id),
    onSuccess: () => {
      toast("Mark scheme range verified.", "success");
      void invalidateList();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const expansionMutation = useMutation({
    mutationFn: () => expandMarkScheme(documentId!),
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openEdit(range: MarkSchemeRange) {
    setEditing(range);
    setForm({
      question_range_start: range.question_range_start,
      question_range_end: range.question_range_end,
      marks_per_question: range.marks_per_question,
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    updateMutation.mutate({
      id: editing.id,
      data: {
        question_range_start: form.question_range_start,
        question_range_end: form.question_range_end,
        marks_per_question: Number(form.marks_per_question),
      },
    });
  }

  const columns: Column<MarkSchemeRange>[] = [
    { key: "question_range_start", header: "From Q#", render: (row) => row.question_range_start },
    { key: "question_range_end", header: "To Q#", render: (row) => row.question_range_end },
    { key: "marks_per_question", header: "Marks / Question", render: (row) => row.marks_per_question },
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

  const expansionEntries = expansionMutation.data
    ? Object.entries(expansionMutation.data.marks_by_question)
    : [];
  const warnings = expansionMutation.data?.warnings ?? [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Mark Scheme Verification"
        description="Verify and correct OCR-extracted mark-scheme ranges for this document."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => expansionMutation.mutate()}
              disabled={expansionMutation.isPending}
            >
              <Sparkles className="h-4 w-4" />
              {expansionMutation.isPending ? "Expanding..." : "Preview Expansion"}
            </Button>
            <Button variant="outline" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-4 w-4" />
              Back to document
            </Button>
          </>
        }
      />

      {documentId && <VerificationStepNav documentId={documentId} current="mark-scheme" />}

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No mark scheme ranges found for this document."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit range ${row.question_range_start}-${row.question_range_end}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canVerify && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Verify range ${row.question_range_start}-${row.question_range_end}`}
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

      {expansionMutation.data && (
        <Card>
          <CardHeader>
            <CardTitle>Expansion Preview</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {warnings.length > 0 && (
              <div
                role="alert"
                className="rounded-md border border-warning/30 bg-warning/10 p-3 text-sm text-warning"
              >
                <p className="mb-1 font-medium">Warnings</p>
                <ul className="list-disc pl-5">
                  {warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question #</TableHead>
                  <TableHead>Max Marks</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expansionEntries.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={2} className="py-6 text-center text-muted-foreground">
                      No per-question marks computed.
                    </TableCell>
                  </TableRow>
                ) : (
                  expansionEntries.map(([questionNumber, marks]) => (
                    <TableRow key={questionNumber}>
                      <TableCell>{questionNumber}</TableCell>
                      <TableCell>{marks}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <FormDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        title="Edit Mark Scheme Range"
        onSubmit={handleSubmit}
        isSubmitting={updateMutation.isPending}
        submitLabel="Save"
      >
        <FormField htmlFor="range-start" label="Question Range Start" required>
          <Input
            id="range-start"
            required
            value={form.question_range_start}
            onChange={(event) => setForm({ ...form, question_range_start: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="range-end" label="Question Range End" required>
          <Input
            id="range-end"
            required
            value={form.question_range_end}
            onChange={(event) => setForm({ ...form, question_range_end: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="marks-per-question" label="Marks per Question" required>
          <Input
            id="marks-per-question"
            type="number"
            step="any"
            min="0"
            required
            value={form.marks_per_question}
            onChange={(event) => setForm({ ...form, marks_per_question: event.target.value })}
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
