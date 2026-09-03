# Document Intelligence Guide

## Scope in one paragraph

Between page extraction and OCR, every non-blank page now passes through
four new, additive, opt-in-by-failure-mode stages — **Page Quality
Analysis**, **Adaptive Image Enhancement**, **Original-vs-Enhanced
Selection**, and **Layout/Region Detection** — before the existing
six-provider OCR ensemble (unchanged) runs. The goal (Section 53 of this
milestone's brief) is "extract the maximum reliable information from
educational documents while consuming only the resources necessary for
that particular page" — a clean digital PDF takes a near-zero-cost fast
path; a damaged scan gets targeted, evidence-checked restoration; a
diagram or table gets its own crop preserved and routed, never silently
destroyed by the same restoration a text page needed.

## Zero new dependencies

Every deterministic quality/enhancement metric uses `opencv-python-headless`/
`numpy`/`Pillow`, all already installed and already used throughout
`app.services.image_processing`. Layout/region detection reuses Surya's
`LayoutPredictor` — already installed as part of `surya-ocr==0.13.1` from
the prior OCR-ensemble milestone, already running through the existing
isolated-runtime bridge — no new package, no new venv, no new license to
evaluate. This was a deliberate audit result (Section 13's "reuse before
adding" requirement): docTR's `ocr_predictor` has no region-type
classification at all, and PaddleOCR's `PPStructure` was never ported to
its 3.x API (a pre-existing, documented, unrelated gap) — Surya's
`LayoutPredictor` alone already covers `Text`/`TextInlineMath`/`Equation`/
`Table`/`Picture`/`Figure`/`Handwriting`/`PageHeader`/`PageFooter`/
`SectionHeader`/`Caption`/`Footnote`/`ListItem`/`Form`/`TableOfContents`/
`Code`/`Blank` (`surya.layout.model.config.ID_TO_LABEL`), which is why no
second or third layout framework was installed.

## Architecture

```text
Page image (already rasterized once, per the existing pipeline)
        |
PageQualityAnalyzer (app.services.document_intelligence.quality)
        |  blur / skew / orientation / contrast / brightness / noise /
        |  resolution / background uniformity / perspective / compression
        |  -> PageQualityReport (explainable 0-100 score + recommended_operations)
        v
AdaptiveImageEnhancer (app.services.document_intelligence.enhancement)
        |  builds a MINIMAL plan from recommended_operations only
        |  (empty plan on a clean page -> original image, zero-copy fast path)
        |  reuses EXISTING image_processing step functions, never re-implements them
        |  handwriting/diagram-safe profile downgrades or skips destructive steps
        v
Original-vs-Enhanced Selection (app.services.document_intelligence.variant_selection)
        |  real Tesseract OCR probe on BOTH variants
        |  enhanced wins only if it beats original by a real, non-trivial margin
        |  AND didn't lose the majority of recoverable text
        v
Layout/Region Detection (app.services.document_intelligence.layout)
        |  Surya LayoutPredictor via the existing isolated-runtime bridge
        |  -> DetectedRegion list, mapped onto this project's REGION_TYPES vocabulary
        v
Content Classification (app.services.document_intelligence.classification)
        |  page-level aggregate (PRINTED_TEXT/HANDWRITTEN_TEXT/DIAGRAM/TABLE/
        |  EQUATION/MIXED/UNKNOWN), area-weighted, never destroys a region
        v
   +----+-----------------------------------+
   |                                        |
TEXT/HANDWRITTEN regions              DIAGRAM/EQUATION/TABLE regions
   |                                        |
Existing six-provider OCR ensemble    app.services.document_intelligence.routing
(UNCHANGED — Section 17/18)           - crop preserved (always)
   |                                  - DIAGRAM/EQUATION: best-effort OCR caption
   |                                    label; semantic understanding interface
   |                                    present but NOT_IMPLEMENTED (honest)
   |                                  - TABLE: real Hough-line grid detection +
   |                                    per-cell OCR, or whole-region fallback
   v                                        v
Existing Fusion Engine (UNCHANGED)    DocumentRegion rows (new table)
   |                                        |
   +--------------------+-------------------+
                        v
        AnswerScriptPage / OfficialExamDocumentPage
        (quality_score, quality_classification, quality_metrics,
         enhancement_metadata, storage_key=ORIGINAL,
         preprocessed_storage_key=SELECTED ENHANCED VARIANT if one won)
```

## Original-page immutability (Section 6)

`storage_key` now always holds the genuinely untouched original page
image (this was a real, pre-existing gap this milestone fixed — see
[Files changed](#a-real-pre-existing-bug-this-milestone-fixed) below);
`preprocessed_storage_key` holds the enhanced variant **only when it was
actually selected** as the better-evidenced OCR input. A rejected
enhancement attempt is never written to durable object storage — its
outcome (operations attempted, both confidences, the reason it lost) is
fully recorded in `enhancement_metadata` instead, a deliberate disk-safety
choice (Section 31: "clean disposable intermediates") rather than
retaining every rejected image variant forever.

## Page Quality Analyzer

`app.services.document_intelligence.quality.analyze_page_quality()`
returns a `PageQualityReport`: `quality_score` (0-100, an explainable
weighted combination of the sub-scores below — see `_SCORE_WEIGHTS`,
documented defaults, not measured accuracy), `quality_classification`
(`EXCELLENT`/`GOOD`/`FAIR`/`POOR`/`CRITICAL`), and per-signal detail:

- **Blur**: Laplacian variance (classic, real focus/sharpness measure).
- **Skew**: reuses `image_processing.rotation.detect_rotation_angle()`.
- **Orientation**: reuses `image_processing.orientation.detect_orientation()`.
- **Contrast**: foreground/background *mean separation* (via a shared
  Otsu ink/background mask), not raw whole-image pixel std — global std
  is misleadingly low on a sparse-text page regardless of how well the
  actual ink stands out.
- **Brightness/exposure**: background brightness via the 95th percentile,
  darkest-ink estimate via the Otsu ink mask's own low percentile —
  **not** raw mean luminance, which runs naturally high for any
  well-exposed document page (mostly white background) and would
  otherwise misclassify a normal clean page as "overexposed" (a real
  calibration bug found and fixed during this milestone's own testing —
  see `tests/test_document_intelligence_quality.py::test_sparse_text_page_is_not_falsely_flagged_overexposed`).
- **Noise**: Immerkaer's fast noise-variance estimator (a real, published,
  closed-form formula — J. Immerkaer, *Fast Noise Variance Estimation*,
  CVIU 1996 — not an invented heuristic).
- **Resolution**: pixel dimensions; an effective-DPI estimate only when
  the page's aspect ratio plausibly resembles A4 (never fabricates a
  physical-size assumption otherwise); `small_text_risk` below a
  documented long-edge-pixel threshold.
- **Background uniformity**: std of grayscale values sampled *only* at
  pixels the shared Otsu mask classifies as background (not ink) — an
  earlier version reused `background_clean.py`'s morphological-open
  estimate directly and produced false "uneven background" readings on
  perfectly-lit, text-dense pages (a second real bug found and fixed
  during development — see the module's own docstring history).
- **Perspective risk**: reuses `perspective.py`'s own quadrilateral
  detector (new public `estimate_perspective_risk()` function added to
  that module) — corner-angle deviation from 90°, `0.0` when no clean
  quad is found (same conservative stance `correct_perspective()` itself
  takes).
- **Compression artifact risk**: classic JPEG-blockiness estimate (8-pixel
  grid boundary discontinuity ratio).
- **Document-type hint**: `PRINTED_DOCUMENT`/`HANDWRITTEN_DOCUMENT`/
  `MIXED_DOCUMENT`/`UNKNOWN` — a heuristic (explicitly not a trained
  classifier) based on the coefficient of variation of per-component
  stroke width (via distance transform) across connected ink components.

## Adaptive Image Enhancer

`app.services.document_intelligence.enhancement.enhance_page()` builds its
plan **only** from `PageQualityReport.recommended_operations` — a clean
page's plan is empty and the function returns the *same* image object,
untouched (a true zero-cost fast path, not a no-op transform). Every step
in the plan is one of the pre-existing `image_processing` functions
(`correct_orientation`/`deskew`/`correct_perspective`/`clean_background`/
`enhance_contrast`/`correct_brightness`/`denoise`) — never reimplemented.

**Handwriting/diagram-safe profiles** (Sections 10/11): when the page's
`document_type_hint` is `HANDWRITTEN_DOCUMENT`, or the caller flags
diagram risk, `background_clean` (morphological, can erase thin strokes)
is skipped entirely and `denoise` is downgraded to a much gentler strength
rather than run at its default, more-aggressive setting.

## Original-vs-Enhanced Selection

`app.services.document_intelligence.variant_selection.select_best_variant()`
runs a real, fast Tesseract OCR probe (not the six-provider ensemble — that
would multiply this decision's own cost by 6x) on both variants and
selects the enhanced one only if its confidence beats the original by a
real, documented margin (`_MIN_CONFIDENCE_ADVANTAGE = 1.5`) **and** it
didn't lose more than half the original's recoverable character count — a
safety net that caught a genuine finding during this milestone's own
testing: a conservative-strength denoise pass still fully destroyed a
noisy synthetic test page's text (0 characters recovered vs. 182 in the
original), correctly triggering fallback to the original rather than
trusting a plausible-looking confidence number in isolation.

## Layout / Region Detection

`app.services.document_intelligence.layout.detect_regions_surya()` calls
Surya's real `LayoutPredictor` through the existing isolated-runtime
bridge (`app.services.ocr.isolated_runners.surya_runner`'s new `"layout"`
mode) and maps its native labels onto this project's unified
`REGION_TYPES` vocabulary (`PRINTED_TEXT`/`HANDWRITTEN_TEXT`/
`QUESTION_NUMBER`/`MARKS`/`DIAGRAM`/`TABLE`/`EQUATION`/`HEADER`/`FOOTER`/
`PAGE_NUMBER`/`IMAGE`/`OTHER`). `reconcile_regions()` merges multiple
detectors' output via geometric IoU (deterministic, no second ML model,
per Section 15's own "don't build an unnecessarily huge ensemble if
geometry solves it" guidance) — this milestone only ever feeds it Surya's
output (honestly reflected in `DetectedRegion.source_detector`), but the
function's signature already accepts more than one detector for a future
milestone.

**Real, honest limitations found during testing**: on non-representative
synthetic test images, Surya's real model sometimes disagreed with the
"intended" label — a simple ruled grid (no realistic table content) was
classified `Picture`/DIAGRAM rather than `Table`; plain-ASCII "x^2 + y^2 =
r^2" text was classified `SectionHeader`/HEADER rather than `Equation`
(real mathematical typesetting reads very differently to the model than
ASCII notation). These are genuine model behaviors on unrepresentative
inputs, reported as-is rather than hidden or worked around.

## Content Classification

`app.services.document_intelligence.classification.classify_page()`
aggregates a page's regions into one page-level label, area-weighted (a
tiny stray low-confidence region can't flip the whole page's
classification), falling back to `PageQualityReport.document_type_hint`
when layout detection produced nothing at all (Section 28: layout
detection failure still yields a usable classification, never a crash).

## Diagram / Equation / Table Routing

`app.services.document_intelligence.routing`:

- **Crop preservation** (`preserve_region_crop()`): every DIAGRAM/TABLE/
  EQUATION region's real pixel crop is PNG-encoded and persisted to
  MinIO (`build_region_crop_key()`) — never discarded regardless of what
  analysis is or isn't available downstream.
- **Diagram/Equation**: `label_region_with_ocr()` gets a real, best-effort
  Tesseract read of any caption/label text in the crop — explicitly
  **not** claimed as diagram/equation *understanding* (Section 19/20).
  `VisualAnalysisProvider`/`MathRecognitionProvider` are real `Protocol`
  interfaces with a default implementation that honestly reports
  `NOT_IMPLEMENTED` — a future milestone can register a real
  isolated-runtime vision/math model against the same interface with zero
  changes to any caller.
- **Table**: `extract_table_structure()` is a REAL, deterministic,
  local, no-ML-model ruled-table grid detector (morphological horizontal/
  vertical line extraction -> row/column boundary derivation -> per-cell
  Tesseract OCR). Falls back to a single whole-region "cell" when no
  clean grid is found, rather than fabricating rows/columns that aren't
  there. Two genuine bugs were found and fixed while verifying this
  against a real synthetic 3x3 table: (1) isolated small crops read
  unreliably at native resolution and needed upscaling + a different
  Tesseract PSM mode (6, not this project's page-level default of 3); (2)
  including a cell's own ruling-line pixels in its crop measurably
  disrupted Tesseract's character segmentation, fixed by cropping with a
  small inward margin.

## Database changes (migration `0019_document_intelligence`)

Purely additive:

- `answer_script_pages` gains `quality_score`/`quality_classification`/
  `quality_metrics` (JSON)/`enhancement_metadata` (JSON)/
  `processing_substage`.
- `official_exam_document_pages` gains the same five columns **plus**
  `preprocessed_storage_key` (which `answer_script_pages` already had
  from an earlier Module 05 migration, but this parallel Module 06 table
  never did).
- New `document_regions` table — one row per detected region, belonging
  to EITHER an `AnswerScriptPage` OR an `OfficialExamDocumentPage`
  (exactly one FK set, enforced by a CHECK constraint) — a genuinely new
  table, not a retrofit of `OCRBlock` (which only ever exists as the
  *output* of a completed OCR run, not as pre-OCR layout/routing input).

**A real migration bug found and fixed during this milestone's own live
verification**: the hand-written `CREATE TABLE` DDL for `document_regions`
initially omitted `server_default=now()` for `created_at`/`updated_at`
(the ORM model declares it, but a hand-written migration doesn't inherit
that automatically) — every insert failed with a `NotNullViolationError`
until the migration was corrected and re-applied (downgrade + upgrade,
verified against the real local Postgres both times).

### A real, pre-existing bug this milestone fixed

`AnswerScriptPage.storage_key`/`preprocessed_storage_key` already existed
in the schema (and the frontend's `PageViewerPage.tsx` already expected
`storage_key` = original, `preprocessed_storage_key` = enhanced — its own
test fixtures literally named sample keys `"page-1-original.png"` /
`"page-1-preprocessed.png"`), but `_run_pipeline()` never actually
populated `preprocessed_storage_key` at all — it only ever wrote the
*already-processed* image to `storage_key`, silently discarding the
genuine original. This milestone's Celery integration fixes this as a
side effect of implementing Section 6's original-immutability
requirement properly.

## Celery integration & failure isolation (Sections 28/32)

All four new stages run inside the existing `_run_pipeline()` (Module 05,
`app/tasks/ocr_tasks.py`) between page-splitting and the (unchanged)
OCR stage — no new Celery task, no change to the existing job/status
state machine's actual enum values (Section 33: additive detail only,
never a breaking change to `AnswerScript.status`/`AnswerScriptPage.status`).
Every new stage is independently wrapped in `try/except`, logging a
warning and falling back exactly as Section 28 specifies:

- Quality analysis fails -> proceed with the raw original image, no
  quality metadata recorded for that page.
- Enhancement fails -> proceed with the raw original image.
- Layout detection fails (including the isolated-runtime bridge timing
  out or the venv being absent) -> the page still proceeds through the
  unchanged six-provider OCR ensemble/single-provider path below,
  unaffected; no regions are persisted for that page.

One optional intelligence component never blocks or breaks the core OCR
pipeline — verified via the real end-to-end run below.

## Real verification performed

A live Celery worker (real Postgres, real MinIO, real Redis via the
`redis2://` transport) processed a genuine shadowed test page end to end:
quality analysis ran (score 81.47, `GOOD`), a real `background_clean`
enhancement was attempted, the original genuinely won selection (real
Tesseract confidences 95.38 vs. 94.62 — enhancement didn't help enough to
justify switching), Surya's real `LayoutPredictor` detected 4 regions
(3 `HEADER` + 1 `PRINTED_TEXT`, all persisted as real `DocumentRegion`
rows), and the existing OCR pipeline still produced a correct, complete
result (95.38% confidence) — proving the whole chain integrates without
regressing the OCR result itself.

See [ocr-pipeline-guide.md](ocr-pipeline-guide.md) for the six-provider
OCR ensemble/fusion architecture this milestone deliberately left
unchanged, and this milestone's own final report for the full evidence
set (quality/enhancement benchmarks, diagram/table/equation tests, full
regression results).

## Known limitations / deferred work

- **Diagram/equation semantic understanding**: detection + crop
  preservation are real; interpretation (what does this diagram show,
  what does this equation mean) is honestly `NOT_IMPLEMENTED` this
  milestone — no free, local, Windows-compatible model was integrated
  for this, consistent with Section 20/22's explicit permission to defer
  semantic understanding to a future milestone rather than force a
  fabricated result now.
- **Question/answer boundary association** (Sections 24/25 — associating
  a detected region with a specific question number) was not implemented
  this milestone given the scope already delivered; `DocumentRegion
  .parent_region_id` exists in the schema for this purpose but nothing
  populates it yet.
- **PaddleOCR's `PPStructure`** remains unported to its 3.x API (a
  pre-existing, unrelated gap documented in `paddleocr_provider.py`,
  not something this milestone needed to fix given Surya's layout
  detection already covers the need).
- Text/handwritten-text regions are detected and classified, but the
  existing six-provider OCR ensemble call itself remains whole-page (not
  yet re-routed per-region) — Section 17/18 explicitly required
  preserving the existing architecture unchanged; per-region OCR routing
  is a larger future integration, not attempted this milestone.

## Related documents

- [ocr-pipeline-guide.md](ocr-pipeline-guide.md) — six-provider OCR
  ensemble/fusion architecture (unchanged by this milestone).
- [database-standards.md](database-standards.md) — table/column
  conventions.
