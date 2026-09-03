# Teacher User Guide — IntelliGrade v1.0

For teachers using IntelliGrade to evaluate student answer scripts and
manage results. For institution setup (users, roles, academic structure),
see `docs/administrator-manual.md`.

## Your typical workflow

```
Verify official exam content → Review AI evaluations → Finalize results → Publish
```

## 1. Verifying official exam content

Before any student answer can be evaluated, the official Question Paper,
Model Answer, and Mark Scheme for an exam need to be uploaded and
verified:

1. Go to **Official Document Upload Dashboard**, upload the Question
   Paper/Model Answer/Mark Scheme PDFs (or scanned images) for the exam.
2. IntelliGrade automatically OCRs them (real Tesseract, not a
   placeholder) into structured questions/model answers/mark-scheme
   ranges — this happens in the background; refresh the dashboard to see
   when it completes.
3. Go to the exam's document detail screen and **verify** each extracted
   question, model answer, and mark-scheme range. This is a required
   step — evaluation reads verified content, not raw OCR output — so
   check the extracted text actually matches the source PDF and correct
   anything the OCR got wrong (handwriting/scan quality can cause
   misreads).

## 2. Answer scripts get evaluated automatically

Once students' answer scripts are uploaded (by them, or by staff on
their behalf) and OCR'd, AI evaluation runs per question, producing a
suggested mark plus a confidence score. You'll see this reflected in your
**Teacher Review Dashboard** queue, bucketed by confidence:

- **High confidence (≥90%)** — auto-suggested, spot-check recommended
  but not mandatory before finalizing.
- **Medium confidence (70–89%)** — needs your explicit confirmation
  before it counts toward a result.
- **Low confidence (<70%)** — mandatory review; the AI's suggestion is a
  starting point, not a default.

## 3. Reviewing an evaluation

Open any evaluation from the dashboard or the Answer Evaluation Detail
screen. You have four actions:

- **Confirm** — accept the AI's suggested marks as-is.
- **Override** — accept the AI's evaluation but change the marks (e.g.
  you disagree with the exact score, but the AI's reasoning was broadly
  right).
- **Reject** — the marks are cleared entirely; you'll need to score this
  question manually. Requires a reason.
- **Rerun** — force the AI to recompute from scratch (e.g. after you've
  corrected the verified model answer/mark scheme). Your previous
  decision is preserved in evaluation history first, so nothing is lost.

A plain re-trigger of evaluation (e.g. from an automated retry) will
**never** silently overwrite a decision you've already made — only an
explicit Rerun can do that.

## 4. Finalizing results

Once every question in a student's exam session has a reviewed
evaluation (confirmed, overridden, or rejected-then-manually-scored):

1. **Finalize** — per student, per exam (all students), or per batch.
   This computes the total and moves the result to `under_review`.
2. **Approve** — moves to `approved`. (You may not have this permission
   depending on your institution's setup — ask your Institution Admin.)
3. **Lock** — moves to `locked`. **After locking, no further evaluation
   edits are possible for that session** — this is intentional, to
   protect result integrity. If you find an error after locking, you'll
   need someone with the `exam_results:unlock` permission (typically
   Institution Admin) to unlock it first.
4. **Publish** — moves to `published`. The student is notified
   automatically and can see their result.

Bulk actions (approve/lock/publish for an entire exam at once) are
available from the Result Finalization screen when you have many
students to process at once.

## 5. Analytics & Reports

- **Analytics Dashboard** — pass/fail rates, confidence distribution,
  how much your overrides differ from the AI's suggestions on average,
  and which questions students found hardest — computed live, always
  current.
- **Reports** — generate a PDF/Excel/CSV report (7 types: student,
  question-wise, teacher-review summary, AI-performance, institution/
  department/course summary). Reports run in the background; check back
  on the Reports screen for the download link once ready.

## 6. Global Search

Use **Global Search** to find a student (by name or roll number),
subject, or question quickly across everything you have access to —
faster than navigating through each management screen.

## Things that might surprise you

- You cannot edit an evaluation once its result is locked — this is by
  design, not a bug. Ask for an unlock if you genuinely need to correct
  something.
- Rejecting an evaluation doesn't delete it — it clears the marks and
  keeps a record, so the AI's original suggestion is still visible for
  context even after you've moved past it.
- The 90%/70% confidence thresholds are fixed for now (not
  per-institution configurable in v1.0) — see `KNOWN_LIMITATIONS.md`.
