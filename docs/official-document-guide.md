# Official Exam Content Ingestion Guide (Module 06)

Module 06 begins from a correction to earlier scope framing: IntelliGrade
does **not** author examinations. The Question Paper, Model Answer, and
Mark Scheme already exist as official PDFs the Exam Cell/Faculty prepared
outside this system. This guide covers the ingestion half of Module 06 —
uploading those documents, OCR'ing them, extracting structured content,
and teacher verification. See
[ai-evaluation-guide.md](ai-evaluation-guide.md) for what happens after
verification (AI evaluation of student answers).

Modules 01–05 are frozen and unmodified by this module — see ADR-035
through ADR-041 in [ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md)
for the full design record, and
[docs/ocr-pipeline-guide.md](ocr-pipeline-guide.md) for the Module 05
pipeline this module reuses at the engine level.

## Scope in one paragraph

A teacher/admin uploads one PDF per document type (`question_paper`,
`model_answer`, `mark_scheme`) against an `Exam` (Module 04 — exam-level,
not per-student, since a question paper belongs to the whole exam sitting,
not any one student's answer script). A new, parallel Celery task OCRs
the document using Module 05's exact engine code, then runs
best-effort extraction heuristics to produce per-question/per-answer/
per-range candidate rows. A teacher then verifies (or edits) each row
before it's trusted for anything downstream — nothing here is
evaluative, and nothing is promoted into Module 04's Question Bank
unless an institution deliberately chooses to.

## Entity hierarchy

```text
Exam (Module 04, exam-level)
└── OfficialExamDocument                 (root: one PDF, one document_type)
    ├── OfficialExamDocumentPage          (× physical page, pipeline-written)
    ├── ExtractedQuestion                  (if document_type="question_paper")
    ├── ExtractedModelAnswer                (if document_type="model_answer")
    └── MarkSchemeRange                      (if document_type="mark_scheme")
```

One `OfficialExamDocument` table serves all three document types
(`document_type` column), not three near-identical tables — the same
consolidation precedent as Module 05's `DocumentMetadata`/`ProcessingStatus`
collapse (ADR-027, extended here as ADR-035).

## Why this isn't `AnswerScript` reused

`AnswerScript` (Module 05) is hard-FK'd to `exam_sessions.id`, and
`ExamSession` is per-student (`UniqueConstraint(exam_id, student_user_id)`).
A Question Paper has no "student" — it belongs to the `Exam` as a whole.
Rather than bend `AnswerScript`'s schema (touching a frozen module) or
misuse it with a fake session, `OfficialExamDocument` is a new, parallel
root entity FK'd directly to `Exam`.

## Original document immutability

`OfficialExamDocument.storage_key` (the uploaded PDF) and `raw_ocr_text`
(the whole-document OCR dump) are both **write-once** — set exactly once
by the ingestion pipeline and never touched again by any teacher-
verification action. Verification only ever mutates the per-item child
rows (`question_text`/`final_marks` on `ExtractedQuestion`, `answer_text`
on `ExtractedModelAnswer`, the range bounds/marks on `MarkSchemeRange`).
This is deliberate, not incidental: "the original document must never be
modified" is enforced by which columns exist where, not by convention.

## Pipeline stages

```text
1. Upload          POST /official-exam-documents (multipart: exam_id +
                    document_type + file) — validates, computes checksum,
                    detects duplicates, stores original file, enqueues
                    the Celery task
2. Image Processing  page extraction (PDF or single image) + preprocessing,
                      reusing Module 05's PreprocessingPipeline exactly —
                      minus the "orientation" step (see below)
3. OCR Engine          reuses Module 05's OCRProviderAdapter/registry
                       exactly (Tesseract) — no new OCR logic anywhere
4. Structured           document-type-specific heuristic extraction:
   Extraction            question/answer boundary detection + printed-
                          marks detection (question_paper), answer
                          segmentation (model_answer), or mark-range
                          parsing (mark_scheme)
5. Teacher              a teacher reviews/edits each extracted row and
   Verification          marks it verified — nothing is authoritative
                          before this step
```

Unlike Module 05's pipeline, this one does **not** persist a full
`OCRResult`/`OCRBlock`/`OCRLine`/`OCRWord` hierarchy — a question paper's
useful output is the structured extraction (questions/answers/ranges),
not a bounding-box-level tree, so each page's OCR text is reconstructed
from the engine's block/line output (see
[Text reconstruction](#text-reconstruction-not-raw_text) below) and
handed straight to the extraction heuristics.

### A real bug found during this module's build: `orientation` false-positive

Module 05's `PreprocessingPipeline` default step list includes an
`orientation` correction step. Live validation during this module's
build found it produces a **false-positive 180-degree flip** on clean,
well-formed single-column printed text — exactly what official exam
documents are — turning perfectly readable OCR input into garbage. Since
`orientation.py` is frozen (Module 05), the fix is a config choice at the
call site: `app/tasks/official_document_tasks.py` explicitly passes a
step list that **excludes** `"orientation"`
(`["deskew", "denoise", "contrast", "brightness", "margin_trim",
"resolution"]`) — exactly the escape hatch ADR-033 built
`PreprocessingPipeline`'s configurable step list for. Official documents
are direct digital scans from the Exam Cell, not photographed answer
sheets, so orientation correction is low-value here regardless.

### Text reconstruction, not `raw_text`

`TesseractProvider.extract()` (Module 05, frozen) builds its
`OCRPageResult.raw_text` field one **word** per line
(`"\n".join(text_parts)` over individually-recognized words) — reasonable
for Module 05's own consumer (the persisted `OCRBlock`/`OCRLine`/`OCRWord`
tree, which never reads `raw_text` as prose), but wrong for this module's
regex-based question/answer boundary detection, which needs genuine
printed-line breaks. `app/tasks/official_document_tasks.py` reconstructs
natural text from `OCRPageResult.blocks[].lines[].text` instead (each
`OCRLineResult.text` is already `" ".join(words)` per real detected
line) — reading the same `OCRPageResult` every provider returns, adding
no new OCR logic.

## Extraction heuristics

`app/services/official_document_extraction_service.py` (new, does not
touch Module 05's `document_structure_service.py`) provides three
functions, all regex-based and deliberately permissive — false positives
and misses are expected and corrected during teacher verification, not
treated as failures:

- `extract_questions_from_text()` — splits on `Q1)`/`Question 2:`/`3)`-style
  markers (same convention as Module 05's `detect_question_markers`),
  plus a best-effort trailing printed-marks annotation (`[2]`,
  `(4 marks)`, `- 5 marks`) per question.
- `extract_answers_from_text()` — same boundary detection, for model
  answers.
- `extract_mark_ranges_from_text()` — parses "Questions 1-12 = 1 mark",
  "Q13-17: 2 marks", "Question 18 to 25 carries 14 marks"-style lines into
  `(start, end, marks)` candidates.

## Mark scheme expansion

`app/services/mark_scheme_service.py` (pure logic, no DB session) turns a
verified list of `MarkSchemeRange` rows into a `{question_number: marks}`
map — the literal "Questions 1-12 = 1 mark" → per-question maximum
conversion the brief requires, supporting any examination pattern since
every range is data, never a hardcoded constant:

```python
expand_mark_scheme_ranges(ranges) -> MarkSchemeExpansionResult
# .marks_by_question: dict[str, Decimal]
# .warnings: list[str]  — e.g. overlapping ranges (later range wins)

validate_coverage(marks_by_question, detected_question_numbers) -> list[str]
# cross-checks against ExtractedQuestion's actual question numbers —
# "you said Q1-25 but the paper only has 20 questions"
```

`GET /mark-scheme-ranges/expand?document_id=` exposes this live — the
frontend's Mark Scheme Verification screen calls it directly rather than
computing anything client-side.

## Question Bank promotion is optional, never required

`ExtractedQuestion.linked_question_id` and
`ExtractedModelAnswer.linked_answer_key_id` are nullable, optional FKs
into Module 04's `questions.id`/`answer_keys.id` bank. Promotion is a
separate, explicitly-triggered action an institution may choose —
**never** a precondition of evaluation (ADR-037). Module 04's `Question`
requires category/type/difficulty/Bloom-level FKs a freshly-OCR'd
question has no way to populate automatically; forcing full bank
curation before evaluation could run would block the workflow on work
the brief never asked for. The Question Bank remains a reusable academic
repository; official exam documents are temporary evaluation assets —
kept completely separate by design.

## RBAC

8 new resource prefixes, 20 permission codes total (of Module 06's 26 —
the other 6 are `ai_providers`/`ai_configurations`, see
[ai-evaluation-guide.md](ai-evaluation-guide.md)):
`official_exam_documents` (create/read/update/delete/retry/cancel),
`official_exam_document_pages` (read), `extracted_questions`/
`extracted_model_answers`/`mark_scheme_ranges` (read/update/verify each).

Students get **zero** default access — official model answers and mark
schemes are more sensitive than Module 05's ungraded scripts (leaking
either before/during an exam window is an integrity issue, not just a
privacy one). Teachers get the full upload + verify workflow;
institution_admin additionally gets delete/retry/cancel.

## Testing

Real, non-mocked Tesseract OCR end-to-end for all three document types
(`tests/test_official_document_tasks.py`) — synthetic rendered-text
images, real preprocessing (minus `orientation`), real extraction. See
[TESTING_STATUS.md](../TESTING_STATUS.md) for the full breakdown.

## Related documents

- [ai-evaluation-guide.md](ai-evaluation-guide.md) — what happens after
  verification.
- [ocr-pipeline-guide.md](ocr-pipeline-guide.md) — the Module 05 OCR
  engine this module reuses exactly.
- [database-standards.md](database-standards.md) — full table list.
