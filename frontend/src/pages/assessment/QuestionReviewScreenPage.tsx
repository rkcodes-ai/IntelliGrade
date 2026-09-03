import { useState, type FormEvent } from "react";
import { ArrowLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { questionReviewsApi } from "@/api/questionReviews";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useAppSelector } from "@/store";
import type { QuestionReview } from "@/types/assessment";

interface ReviewFormState {
  comment: string;
  rating: string;
}

const emptyForm: ReviewFormState = { comment: "", rating: "" };

function truncate(text: string, length = 100) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function renderStars(rating: number | null) {
  if (rating === null) return "—";
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

/**
 * Peer review comments/ratings scoped to a single question, reached from the
 * Question Viewer's "View Reviews" link. `questionReviewsApi` has no
 * server-side filter-by-question-id param, so this fetches a large page and
 * filters client-side — same nested/child-resource approach used by the
 * Blueprint/Paper/Rubric builders, except here the "parent" is just the route
 * param (already selected), not a second table on this page.
 */
export function QuestionReviewScreenPage() {
  const { id: questionId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("question_reviews:create");
  const canUpdate = permissions.includes("question_reviews:update");
  const canDelete = permissions.includes("question_reviews:delete");

  const list = usePaginatedList<QuestionReview>({
    queryKey: "question-reviews",
    fetcher: (params) => questionReviewsApi.list({ ...params, page_size: 200 }),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "question-reviews",
    questionReviewsApi,
    "Review",
  );

  const reviews = list.items.filter((review) => review.question_id === questionId);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<QuestionReview | null>(null);
  const [form, setForm] = useState<ReviewFormState>(emptyForm);
  const [deleting, setDeleting] = useState<QuestionReview | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(review: QuestionReview) {
    setEditing(review);
    setForm({ comment: review.comment, rating: review.rating === null ? "" : String(review.rating) });
    setFormOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const rating = form.rating === "" ? null : Number(form.rating);
    if (editing) {
      updateMutation.mutate(
        { id: editing.id, data: { comment: form.comment, rating } },
        { onSuccess: () => setFormOpen(false) },
      );
    } else if (questionId) {
      createMutation.mutate(
        { question_id: questionId, comment: form.comment, rating },
        { onSuccess: () => setFormOpen(false) },
      );
    }
  }

  const columns: Column<QuestionReview>[] = [
    { key: "comment", header: "Comment", render: (row) => truncate(row.comment) },
    { key: "rating", header: "Rating", render: (row) => renderStars(row.rating) },
    { key: "created_at", header: "Created At", render: (row) => new Date(row.created_at).toLocaleDateString() },
  ];

  return (
    <div>
      <PageHeader
        title="Question Reviews"
        description="Peer review comments and ratings for this question."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-4 w-4" />
              Back to question
            </Button>
            {canCreate && (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" />
                New Review
              </Button>
            )}
          </div>
        }
      />

      <DataTable
        columns={columns}
        rows={reviews}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No reviews found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button variant="ghost" size="icon" aria-label={`Edit review ${row.id}`} onClick={() => openEdit(row)}>
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete review ${row.id}`}
                onClick={() => setDeleting(row)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      />

      <FormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editing ? "Edit Review" : "New Review"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="review-comment" label="Comment" required>
          <Textarea
            id="review-comment"
            required
            value={form.comment}
            onChange={(event) => setForm({ ...form, comment: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="review-rating" label="Rating">
          <Input
            id="review-rating"
            type="number"
            min={1}
            max={5}
            value={form.rating}
            onChange={(event) => setForm({ ...form, rating: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete review?"
        description="This review will be soft-deleted and can be restored later."
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
