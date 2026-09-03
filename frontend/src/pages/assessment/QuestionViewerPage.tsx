import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, History, Pencil, Plus, Send, X } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { bloomTaxonomyLevelsApi } from "@/api/bloomTaxonomyLevels";
import { difficultyLevelsApi } from "@/api/difficultyLevels";
import { questionCategoriesApi } from "@/api/questionCategories";
import {
  addQuestionTag,
  createQuestionVersionSnapshot,
  questionsApi,
  removeQuestionTag,
  submitQuestionForReview,
} from "@/api/questions";
import { questionTagsApi } from "@/api/questionTags";
import { questionTypesApi } from "@/api/questionTypes";
import { subjectsApi } from "@/api/subjects";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/ToastProvider";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { QuestionTagMapRead, QuestionVersionSnapshotRequest } from "@/types/assessment";

function MetadataItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}

/**
 * Read-only detail view of a single `Question`. Create/edit lives on a
 * separate Question Editor screen — this page only displays fields, resolves
 * lookup ids to names, and exposes workflow actions (submit for review,
 * version snapshot, tagging). There is no GET-tags-for-question endpoint, so
 * the tags list here tracks only what's been added during this session.
 */
export function QuestionViewerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canUpdate = permissions.includes("questions:update");

  const {
    data: question,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["questions", id],
    queryFn: () => questionsApi.get(id!),
    enabled: Boolean(id),
  });

  const { data: subjects } = useSelectOptions("subjects", () => subjectsApi.list({ page_size: 200 }));
  const { data: categories } = useSelectOptions("question-categories", () =>
    questionCategoriesApi.list({ page_size: 200 }),
  );
  const { data: types } = useSelectOptions("question-types", () =>
    questionTypesApi.list({ page_size: 200 }),
  );
  const { data: difficulties } = useSelectOptions("difficulty-levels", () =>
    difficultyLevelsApi.list({ page_size: 200 }),
  );
  const { data: bloomLevels } = useSelectOptions("bloom-taxonomy-levels", () =>
    bloomTaxonomyLevelsApi.list({ page_size: 200 }),
  );
  const { data: tags } = useSelectOptions("question-tags", () => questionTagsApi.list({ page_size: 200 }));

  const [sessionTags, setSessionTags] = useState<QuestionTagMapRead[]>([]);
  const [selectedTagId, setSelectedTagId] = useState("");
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const [changeReason, setChangeReason] = useState("");

  function invalidateQuestion() {
    return queryClient.invalidateQueries({ queryKey: ["questions", id] });
  }

  const submitMutation = useMutation({
    mutationFn: () => submitQuestionForReview(id!),
    onSuccess: () => {
      toast("Question submitted for review.", "success");
      void invalidateQuestion();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const addTagMutation = useMutation({
    mutationFn: (tagId: string) => addQuestionTag(id!, { tag_id: tagId }),
    onSuccess: (data) => {
      setSessionTags((prev) => [...prev, data]);
      setSelectedTagId("");
      toast("Tag added.", "success");
      void invalidateQuestion();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const removeTagMutation = useMutation({
    mutationFn: (tagId: string) => removeQuestionTag(id!, tagId),
    onSuccess: (_data, tagId) => {
      setSessionTags((prev) => prev.filter((sessionTag) => sessionTag.tag_id !== tagId));
      toast("Tag removed.", "success");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const snapshotMutation = useMutation({
    mutationFn: (payload: QuestionVersionSnapshotRequest) => createQuestionVersionSnapshot(id!, payload),
    onSuccess: () => {
      toast("Version snapshot created.", "success");
      void invalidateQuestion();
      setSnapshotOpen(false);
      setChangeReason("");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function handleSnapshotSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    snapshotMutation.mutate({ change_reason: changeReason.trim() || undefined });
  }

  const subjectName = (subjectId: string) => subjects?.find((s) => s.id === subjectId)?.name ?? subjectId;
  const categoryName = (categoryId: string) =>
    categories?.find((c) => c.id === categoryId)?.name ?? categoryId;
  const typeName = (typeId: string) => types?.find((t) => t.id === typeId)?.name ?? typeId;
  const difficultyName = (difficultyId: string) =>
    difficulties?.find((d) => d.id === difficultyId)?.name ?? difficultyId;
  const bloomName = (bloomId: string) => bloomLevels?.find((b) => b.id === bloomId)?.name ?? bloomId;
  const tagName = (tagId: string) => tags?.find((t) => t.id === tagId)?.name ?? tagId;

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <Spinner />
      </div>
    );
  }

  if (isError || !question) {
    return <p className="p-6 text-sm text-muted-foreground">Question not found.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Question Detail"
        description="Read-only detail view of a question in the question bank."
        actions={
          <>
            {canUpdate && (
              <Button variant="outline" onClick={() => navigate(`/dashboard/questions/${id}/edit`)}>
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            )}
            {canUpdate && question.approval_status === "draft" && (
              <Button onClick={() => submitMutation.mutate()} disabled={submitMutation.isPending}>
                <Send className="h-4 w-4" />
                Submit for Review
              </Button>
            )}
            <Button variant="outline" onClick={() => navigate(`/dashboard/questions/${id}/reviews`)}>
              <Eye className="h-4 w-4" />
              View Reviews
            </Button>
            {canUpdate && (
              <Button variant="outline" onClick={() => setSnapshotOpen(true)}>
                <History className="h-4 w-4" />
                Create Version Snapshot
              </Button>
            )}
          </>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>Question</CardTitle>
              <CardDescription>Version v{question.current_version}</CardDescription>
            </div>
            <Badge variant={statusVariant(question.approval_status)} className="h-fit shrink-0">
              {formatStatusLabel(question.approval_status)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <p className="text-lg font-medium">{question.question_text}</p>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <MetadataItem label="Subject" value={subjectName(question.subject_id)} />
            <MetadataItem label="Category" value={categoryName(question.question_category_id)} />
            <MetadataItem label="Type" value={typeName(question.question_type_id)} />
            <MetadataItem label="Difficulty" value={difficultyName(question.difficulty_level_id)} />
            <MetadataItem label="Bloom Level" value={bloomName(question.bloom_level_id)} />
            <MetadataItem label="Unit" value={question.unit ?? "—"} />
            <MetadataItem label="Chapter" value={question.chapter ?? "—"} />
            <MetadataItem label="Topic" value={question.topic ?? "—"} />
            <MetadataItem label="Subtopic" value={question.subtopic ?? "—"} />
            <MetadataItem label="Learning Outcome" value={question.learning_outcome ?? "—"} />
            <MetadataItem label="Marks" value={question.marks} />
            <MetadataItem
              label="Estimated Time"
              value={
                question.estimated_time_minutes != null ? `${question.estimated_time_minutes} min` : "—"
              }
            />
            <MetadataItem label="Language" value={question.language} />
            <MetadataItem
              label="Diagram URL"
              value={
                question.diagram_url ? (
                  <a
                    href={question.diagram_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline"
                  >
                    {question.diagram_url}
                  </a>
                ) : (
                  "—"
                )
              }
            />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tags</CardTitle>
          <CardDescription>Tags added during this session.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {sessionTags.length === 0 && (
              <p className="text-sm text-muted-foreground">No tags added yet.</p>
            )}
            {sessionTags.map((sessionTag) => (
              <span
                key={sessionTag.id}
                className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs"
              >
                {tagName(sessionTag.tag_id)}
                <button
                  type="button"
                  aria-label={`Remove tag ${tagName(sessionTag.tag_id)}`}
                  onClick={() => removeTagMutation.mutate(sessionTag.tag_id)}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
          {canUpdate && (
            <div className="flex items-center gap-2">
              <Select
                aria-label="Select tag to add"
                value={selectedTagId}
                onChange={(event) => setSelectedTagId(event.target.value)}
                className="w-auto"
              >
                <option value="">Select a tag…</option>
                {tags?.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.name}
                  </option>
                ))}
              </Select>
              <Button
                type="button"
                size="sm"
                disabled={!selectedTagId || addTagMutation.isPending}
                onClick={() => addTagMutation.mutate(selectedTagId)}
              >
                <Plus className="h-4 w-4" />
                Add
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <FormDialog
        open={snapshotOpen}
        onOpenChange={setSnapshotOpen}
        title="Create Version Snapshot"
        description="Optionally record why this snapshot is being taken."
        onSubmit={handleSnapshotSubmit}
        isSubmitting={snapshotMutation.isPending}
        submitLabel="Create Snapshot"
      >
        <FormField htmlFor="snapshot-change-reason" label="Change Reason">
          <Textarea
            id="snapshot-change-reason"
            value={changeReason}
            onChange={(event) => setChangeReason(event.target.value)}
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
