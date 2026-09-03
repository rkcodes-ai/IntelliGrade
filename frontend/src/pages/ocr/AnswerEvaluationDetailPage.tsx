import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import {
  confirmAnswerEvaluation,
  getAnswerEvaluation,
  overrideAnswerEvaluation,
  rejectAnswerEvaluation,
  rerunAnswerEvaluation,
} from "@/api/answerEvaluations";
import { getExtractedModelAnswer } from "@/api/extractedModelAnswers";
import { DetailLoading, DetailNotFound } from "@/components/common/DetailState";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/ToastProvider";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { AnswerEvaluation } from "@/types/officialExam";

/**
 * The 7 AI signals computed by `AnswerEvaluationService` (ADR-039) — each
 * must remain individually visible, never collapsed into a single number,
 * so teachers can see *why* a suggested mark was produced.
 */
const SIGNALS: Array<{ key: keyof AnswerEvaluation; label: string }> = [
  { key: "semantic_similarity_score", label: "Semantic Similarity" },
  { key: "keyword_match_score", label: "Keyword Match" },
  { key: "concept_match_score", label: "Concept Match" },
  { key: "reasoning_score", label: "Reasoning" },
  { key: "completeness_score", label: "Completeness" },
  { key: "relevance_score", label: "Relevance" },
  { key: "confidence_score", label: "Confidence" },
];

function scorePercent(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return null;
  return Math.round(parsed * 100);
}

function SignalScore({ label, value }: { label: string; value: string | null }) {
  const percent = scorePercent(value);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
        <span className="font-mono text-sm">{percent != null ? `${percent}%` : "—"}</span>
      </div>
      <ProgressBar percent={percent ?? 0} />
    </div>
  );
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
 * Read-only-plus-review detail view of a single `AnswerEvaluation`. Renders
 * all 7 AI signal scores individually (ADR-039 explainability requirement),
 * the student's answer, the matched model answer's question number (if
 * any), and the two Teacher Review actions (ADR-040): Confirm and Override.
 */
export function AnswerEvaluationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canConfirm = permissions.includes("answer_evaluations:confirm");
  const canOverride = permissions.includes("answer_evaluations:override");
  const canReject = permissions.includes("answer_evaluations:reject");
  const canRerun = permissions.includes("answer_evaluations:rerun");

  const [overrideOpen, setOverrideOpen] = useState(false);
  const [finalMarks, setFinalMarks] = useState("");
  const [notes, setNotes] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const {
    data: evaluation,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["answer-evaluations", id],
    queryFn: () => getAnswerEvaluation(id!),
    enabled: Boolean(id),
  });

  const { data: modelAnswer } = useQuery({
    queryKey: ["extracted-model-answers", evaluation?.extracted_model_answer_id],
    queryFn: () => getExtractedModelAnswer(evaluation!.extracted_model_answer_id!),
    enabled: Boolean(evaluation?.extracted_model_answer_id),
  });

  function invalidateEvaluation() {
    return queryClient.invalidateQueries({ queryKey: ["answer-evaluations", id] });
  }

  const confirmMutation = useMutation({
    mutationFn: () => confirmAnswerEvaluation(id!),
    onSuccess: () => {
      toast("Answer evaluation confirmed.", "success");
      void invalidateEvaluation();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const overrideMutation = useMutation({
    mutationFn: () =>
      overrideAnswerEvaluation(id!, {
        final_marks: Number(finalMarks),
        notes: notes.trim() ? notes.trim() : null,
      }),
    onSuccess: () => {
      toast("Answer evaluation overridden.", "success");
      setOverrideOpen(false);
      void invalidateEvaluation();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectAnswerEvaluation(id!, { reason: rejectReason.trim() }),
    onSuccess: () => {
      toast("Answer evaluation rejected.", "success");
      setRejectOpen(false);
      void invalidateEvaluation();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const rerunMutation = useMutation({
    mutationFn: () => rerunAnswerEvaluation(id!),
    onSuccess: () => {
      toast("AI evaluation re-run — a fresh suggestion is now available for review.", "success");
      void invalidateEvaluation();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openOverride() {
    setFinalMarks(evaluation?.final_marks ?? evaluation?.suggested_marks ?? "");
    setNotes(evaluation?.notes ?? "");
    setOverrideOpen(true);
  }

  function handleOverrideSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    overrideMutation.mutate();
  }

  function openReject() {
    setRejectReason("");
    setRejectOpen(true);
  }

  function handleRejectSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    rejectMutation.mutate();
  }

  if (isLoading) {
    return <DetailLoading />;
  }

  if (isError || !evaluation) {
    return <DetailNotFound message="Answer evaluation not found." />;
  }

  const canShowConfirm = canConfirm && evaluation.suggested_marks != null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Answer Evaluation Detail"
        description="AI-generated evaluation signals and Teacher Review actions for one student answer."
        actions={
          <>
            {canShowConfirm && (
              <Button onClick={() => confirmMutation.mutate()} disabled={confirmMutation.isPending}>
                {confirmMutation.isPending ? "Confirming..." : "Confirm"}
              </Button>
            )}
            {canOverride && (
              <Button variant="outline" onClick={openOverride}>
                Override
              </Button>
            )}
            {canReject && (
              <Button variant="outline" onClick={openReject}>
                Reject
              </Button>
            )}
            {canRerun && (
              <Button
                variant="outline"
                onClick={() => rerunMutation.mutate()}
                disabled={rerunMutation.isPending}
              >
                {rerunMutation.isPending ? "Re-running..." : "Re-run AI Evaluation"}
              </Button>
            )}
          </>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <CardTitle>Overview</CardTitle>
            <Badge
              variant={evaluation.confidence_tier ? statusVariant(evaluation.confidence_tier) : "default"}
              className="h-fit shrink-0"
            >
              {evaluation.confidence_tier ?? "unrated"} confidence
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <MetadataItem label="Exam Session" value={evaluation.exam_session_id} />
            <MetadataItem
              label="Matched Model Answer Question"
              value={modelAnswer?.question_number ?? "—"}
            />
            <MetadataItem
              label="Review Status"
              value={
                <Badge variant={statusVariant(evaluation.review_status)}>
                  {formatStatusLabel(evaluation.review_status)}
                </Badge>
              }
            />
            <MetadataItem label="Suggested Marks" value={evaluation.suggested_marks ?? "—"} />
            <MetadataItem label="Final Marks" value={evaluation.final_marks ?? "—"} />
            <MetadataItem label="Max Marks" value={evaluation.max_marks} />
          </dl>
          {evaluation.notes && (
            <div className="rounded-md border border-border bg-secondary/50 p-3 text-sm">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Notes</p>
              {evaluation.notes}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI Signal Scores</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {SIGNALS.map((signal) => (
              <SignalScore
                key={signal.key}
                label={signal.label}
                value={evaluation[signal.key] as string | null}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Student Answer</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-sm">{evaluation.student_answer_text ?? "—"}</p>
        </CardContent>
      </Card>

      <FormDialog
        open={overrideOpen}
        onOpenChange={setOverrideOpen}
        title="Override Marks"
        description="Record the final marks awarded and an optional reason for overriding the AI suggestion."
        onSubmit={handleOverrideSubmit}
        isSubmitting={overrideMutation.isPending}
        submitLabel="Save Override"
      >
        <FormField htmlFor="override-final-marks" label="Final Marks" required>
          <Input
            id="override-final-marks"
            type="number"
            required
            min="0"
            step="0.01"
            value={finalMarks}
            onChange={(event) => setFinalMarks(event.target.value)}
          />
        </FormField>
        <FormField htmlFor="override-notes" label="Notes (optional)">
          <Textarea
            id="override-notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </FormField>
      </FormDialog>

      <FormDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        title="Reject Evaluation"
        description="Discard this AI evaluation entirely. The original AI-suggested marks are kept for reference, but final marks are cleared until this question is re-run or manually overridden."
        onSubmit={handleRejectSubmit}
        isSubmitting={rejectMutation.isPending}
        submitLabel="Confirm Rejection"
      >
        <FormField htmlFor="reject-reason" label="Reason" required>
          <Textarea
            id="reject-reason"
            required
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
