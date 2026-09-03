import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import {
  approveAIReferenceAnswer,
  generateAIReferenceAnswer,
  getCurrentAIReferenceAnswerForQuestion,
  listAIReferenceAnswerVersions,
  regenerateAIReferenceAnswer,
  rejectAIReferenceAnswer,
} from "@/api/aiReferenceAnswers";
import { getExtractedQuestion } from "@/api/extractedQuestions";
import { DetailLoading, DetailNotFound } from "@/components/common/DetailState";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/ToastProvider";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { AIReferenceStructuredContent } from "@/types/aiReferenceAnswer";

/** Right-column sub-sections — every field from `ReferenceContentSchema`
 * (Phase 4's structured-output contract), each rendered even when empty
 * so a teacher can see what the AI genuinely didn't produce rather than
 * a silently missing section. */
const STRUCTURED_SECTIONS: Array<{ key: keyof AIReferenceStructuredContent; label: string }> = [
  { key: "required_concepts", label: "Required Concepts" },
  { key: "optional_concepts", label: "Optional Concepts" },
  { key: "keywords", label: "Keywords" },
  { key: "equivalent_terms", label: "Equivalent Terminology" },
  { key: "alternative_valid_answers", label: "Alternative Valid Answers" },
  { key: "expected_reasoning", label: "Expected Reasoning" },
  { key: "common_misconceptions", label: "Common Misconceptions" },
  { key: "scoring_guidance", label: "Mark-Aware Scoring Guidance" },
];

function StructuredList({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {items.length > 0 ? (
        <ul className="list-inside list-disc space-y-1 text-sm">
          {items.map((item, index) => (
            // Structured content is AI-generated free text with no stable
            // id — index is safe here since this list is read-only and
            // only ever fully replaced (a new reference version), never
            // reordered/edited in place.
            <li key={index}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">None identified.</p>
      )}
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
 * Phase 10 (AI Reference Answer Builder milestone): three-column review
 * screen for one `ExtractedQuestion`'s AI Reference Answer — Question +
 * Official Model Answer (left), the AI-generated reference (center),
 * and its structured concepts/keywords/alternatives/scoring guidance
 * (right). Teacher Verification actions (Approve/Reject/Regenerate,
 * Phase 7) act on the current version; version history is listed below.
 *
 * The official Model Answer is never replaced by the AI reference — see
 * the backend model's "CRITICAL PRINCIPLE" docstring — this page always
 * renders both side by side, never one in place of the other.
 */
export function AIReferenceAnswerReviewPage() {
  const { extractedQuestionId } = useParams<{ extractedQuestionId: string }>();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("ai_reference_answers:create");
  const canApprove = permissions.includes("ai_reference_answers:approve");
  const canReject = permissions.includes("ai_reference_answers:reject");
  const canRegenerate = permissions.includes("ai_reference_answers:regenerate");

  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const {
    data: question,
    isLoading: isQuestionLoading,
    isError: isQuestionError,
  } = useQuery({
    queryKey: ["extracted-questions", extractedQuestionId],
    queryFn: () => getExtractedQuestion(extractedQuestionId!),
    enabled: Boolean(extractedQuestionId),
  });

  const { data: reference, isLoading: isReferenceLoading } = useQuery({
    queryKey: ["ai-reference-answers", "current", extractedQuestionId],
    queryFn: () => getCurrentAIReferenceAnswerForQuestion(extractedQuestionId!),
    enabled: Boolean(extractedQuestionId),
  });

  const { data: versions } = useQuery({
    queryKey: ["ai-reference-answers", "versions", extractedQuestionId],
    queryFn: () => listAIReferenceAnswerVersions(extractedQuestionId!),
    enabled: Boolean(extractedQuestionId),
  });

  function invalidateAll() {
    void queryClient.invalidateQueries({
      queryKey: ["ai-reference-answers", "current", extractedQuestionId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["ai-reference-answers", "versions", extractedQuestionId],
    });
  }

  const generateMutation = useMutation({
    mutationFn: () => generateAIReferenceAnswer({ extracted_question_id: extractedQuestionId! }),
    onSuccess: () => {
      toast("AI reference answer generated — pending teacher verification.", "success");
      invalidateAll();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateAIReferenceAnswer(extractedQuestionId!),
    onSuccess: () => {
      toast("A new AI reference answer version was generated.", "success");
      invalidateAll();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const approveMutation = useMutation({
    mutationFn: () => approveAIReferenceAnswer(reference!.id),
    onSuccess: () => {
      toast("AI reference answer approved for evaluation.", "success");
      invalidateAll();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectAIReferenceAnswer(reference!.id, { reason: rejectReason.trim() }),
    onSuccess: () => {
      toast("AI reference answer rejected.", "success");
      setRejectOpen(false);
      invalidateAll();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openReject() {
    setRejectReason("");
    setRejectOpen(true);
  }

  function handleRejectSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    rejectMutation.mutate();
  }

  if (isQuestionLoading || isReferenceLoading) {
    return <DetailLoading />;
  }

  if (isQuestionError || !question) {
    return <DetailNotFound message="Extracted question not found." />;
  }

  const canShowApproveReject = reference?.status === "pending_verification";
  const structured = reference?.structured_content;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="AI Reference Answer Review"
        description="Review the AI-synthesized evaluation reference built from the official model answer, and verify it before it is used for evaluation."
        actions={
          <>
            {!reference && canCreate && (
              <Button
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                {generateMutation.isPending ? "Generating..." : "Generate Reference"}
              </Button>
            )}
            {reference && canShowApproveReject && canApprove && (
              <Button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending ? "Approving..." : "Approve"}
              </Button>
            )}
            {reference && canShowApproveReject && canReject && (
              <Button variant="outline" onClick={openReject}>
                Reject
              </Button>
            )}
            {reference && canRegenerate && (
              <Button
                variant="outline"
                onClick={() => regenerateMutation.mutate()}
                disabled={regenerateMutation.isPending}
              >
                {regenerateMutation.isPending ? "Regenerating..." : "Regenerate"}
              </Button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Question &amp; Official Model Answer</CardTitle>
            <CardDescription>
              The authoritative source — the AI reference never replaces this.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <dl className="grid grid-cols-2 gap-4">
              <MetadataItem label="Question #" value={question.question_number} />
              <MetadataItem label="Max Marks" value={question.final_marks ?? "—"} />
            </dl>
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Question Text
              </p>
              <p className="whitespace-pre-wrap text-sm">{question.question_text}</p>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Official Model Answer
              </p>
              {reference ? (
                <p className="whitespace-pre-wrap text-sm">
                  {reference.official_model_answer_text}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Generate an AI reference answer to load the linked official model answer here.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>AI-Generated Reference</CardTitle>
                <CardDescription>Used as the evaluation reference once approved.</CardDescription>
              </div>
              {reference && (
                <Badge variant={statusVariant(reference.status)} className="h-fit shrink-0">
                  {formatStatusLabel(reference.status)}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {!reference ? (
              <p className="text-sm text-muted-foreground">
                No AI reference answer has been generated for this question yet.
              </p>
            ) : (
              <>
                <dl className="grid grid-cols-2 gap-4">
                  <MetadataItem label="Version" value={reference.version} />
                  <MetadataItem
                    label="Confidence"
                    value={
                      reference.generation_confidence != null
                        ? `${reference.generation_confidence}%`
                        : "—"
                    }
                  />
                  <MetadataItem label="Provider Model" value={reference.provider_model ?? "—"} />
                  <MetadataItem
                    label="Generated At"
                    value={
                      reference.generated_at
                        ? new Date(reference.generated_at).toLocaleString()
                        : "—"
                    }
                  />
                </dl>
                {reference.has_conflict_flag && (
                  <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide">
                      Conflict With Official Answer
                    </p>
                    {reference.conflict_notes ??
                      "The AI flagged a possible conflict but did not provide details."}
                  </div>
                )}
                {reference.status === "generation_failed" && reference.generation_error && (
                  <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide">
                      Generation Failed
                    </p>
                    {reference.generation_error}
                  </div>
                )}
                {reference.status === "rejected" && reference.rejection_reason && (
                  <div className="rounded-md border border-border bg-secondary/50 p-3 text-sm">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Rejection Reason
                    </p>
                    {reference.rejection_reason}
                  </div>
                )}
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Synthesized Reference Answer
                  </p>
                  <p className="whitespace-pre-wrap text-sm">
                    {reference.synthesized_reference_answer ?? "—"}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Concepts, Keywords &amp; Marking Guidance</CardTitle>
            <CardDescription>The AI's structured expansion around the official answer.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {structured ? (
              STRUCTURED_SECTIONS.map((section) => (
                <StructuredList
                  key={section.key}
                  label={section.label}
                  items={structured[section.key]}
                />
              ))
            ) : (
              <p className="text-sm text-muted-foreground">
                No structured content available yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {versions && versions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Version History</CardTitle>
            <CardDescription>
              Every past version is kept — an evaluation always stays traceable to the exact
              version that produced it.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {versions.map((version) => (
                <li
                  key={version.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3 text-sm"
                >
                  <span className="font-medium">Version {version.version}</span>
                  <span className="text-muted-foreground">
                    {version.generated_at ? new Date(version.generated_at).toLocaleString() : "—"}
                  </span>
                  <div className="flex items-center gap-2">
                    {version.is_current && <Badge variant="primary">Current</Badge>}
                    <Badge variant={statusVariant(version.status)}>
                      {formatStatusLabel(version.status)}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <FormDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        title="Reject AI Reference Answer"
        description="Record why this reference is being rejected. It will no longer be eligible for evaluation until a new version is generated and approved."
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
