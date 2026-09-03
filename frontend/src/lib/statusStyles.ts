import type { BadgeProps } from "@/components/ui/badge";

type Variant = NonNullable<BadgeProps["variant"]>;

/**
 * One shared status→color mapping for every status/tier enum in the app
 * (job statuses, verification statuses, confidence tiers, review statuses,
 * result states). Previously this exact mapping logic was hand-duplicated
 * per page (`verificationBadgeClassName` in each of the 3 verification
 * screens, `tierClassName` in 3 evaluation-related screens, `statusClassName`
 * variants elsewhere) — consolidated here so every page renders the same
 * status the same color. All keys are unique across their source enums, so
 * one flat map is safe (see the enums in `types/officialExam.ts` and
 * `types/teacherReview.ts`).
 */
const STATUS_VARIANTS: Record<string, Variant> = {
  // Job statuses (OCR jobs, upload jobs, report jobs)
  queued: "info",
  pending: "default",
  running: "info",
  in_progress: "info",
  processing: "info",
  completed: "success",
  failed: "danger",
  cancelled: "outline",
  // Official exam document / answer script ingestion pipeline (longer
  // status chains than a plain job)
  uploading: "info",
  uploaded: "info",
  validating: "info",
  validated: "info",
  failed_validation: "danger",
  storing: "info",
  stored: "info",
  preprocessing: "info",
  ocr_queued: "info",
  ocr_running: "info",
  ocr_complete: "success",
  ocr_failed: "danger",
  structuring: "info",
  // Answer evaluation review statuses
  pending_review: "warning",
  pending_confirmation: "warning",
  auto_suggested: "primary",
  teacher_confirmed: "success",
  teacher_overridden: "info",
  teacher_rejected: "danger",
  // Verification statuses (extracted questions/model answers/mark schemes)
  verified: "success",
  edited: "info",
  rejected: "danger",
  // AI Reference Answer lifecycle (generation + Teacher Verification)
  generating: "info",
  generation_failed: "danger",
  pending_verification: "warning",
  // Confidence tiers
  high: "success",
  medium: "warning",
  low: "danger",
  // Exam result state machine / question & question-paper approval flow
  draft: "default",
  under_review: "warning",
  approved: "success",
  locked: "info",
  published: "success",
  archived: "outline",
};

/** Maps any status/tier string in the app to a consistent `Badge` variant. */
export function statusVariant(status: string): Variant {
  return STATUS_VARIANTS[status] ?? "default";
}

/** "teacher_rejected" -> "teacher rejected" */
export function formatStatusLabel(status: string): string {
  return status.replace(/_/g, " ");
}
