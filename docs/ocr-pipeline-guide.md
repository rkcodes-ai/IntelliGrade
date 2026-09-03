# Answer Script OCR Pipeline Guide (Module 05)

The OCR Pipeline converts an uploaded answer script (PDF or image) into a
structured, machine-readable representation that Module 06 (AI Evaluation)
will consume. It sits on top of the frozen Module 01–04 layers, introduces
11 new entities scoped underneath the existing `Institution` tenant root,
and reuses Module 03/04's tenancy/repository/service/RBAC/audit
infrastructure completely unmodified (see ADR-026 in
[ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md)).

**This module does not evaluate, score, or grade any answer content.** It
only prepares `AnswerScript.structured_content` for a future Module 06 to
read.

## Scope in one paragraph

A teacher/proctor uploads a scanned answer booklet (`AnswerScript`) for a
student's `ExamSession` (Module 04). The pipeline validates the file,
stores it, extracts each page as an image, preprocesses each page
(deskew/denoise/contrast/etc.), runs OCR against each non-blank page,
normalizes the extracted text, and assembles a per-page,
block→line→word structured JSON tree. Every stage transition is logged to
an append-only `ProcessingHistory` table, and the whole pipeline (Stages
4–8) runs as a single Celery background task.

## Pipeline stages

```text
1. Upload            POST /answer-scripts (multipart) — validates, computes
                      checksum, detects duplicates, stores original file,
                      enqueues the Celery task
2. Validation         format/size/page-count checks (synchronous, at upload time)
3. Storage             MinIO, via StorageService (see storage-guide.md)
4. Image Processing     page extraction (PDF or single image) + a configurable
                         preprocessing pipeline per page
5. OCR Engine             TesseractProvider (or any other registered adapter)
                          extracts text/blocks/lines/words/bounding boxes
6. Document Structure       question-marker detection, block/line/word tree
   Extraction
7. Text Normalization         whitespace/unicode/line-ending/hyphenation
                               cleanup — raw AND normalized text both kept
8. Structured Output           AnswerScript.structured_content JSON tree
   Generation
```

Stages 4–8 all run inside one Celery task, `ocr.process_answer_script`
(`app/tasks/ocr_tasks.py::process_answer_script_task` →
`_run_pipeline`), dispatched by `AnswerScriptService.upload()` immediately
after Stage 1–3 complete synchronously in the request/response cycle.

## Entity list and hierarchy

```text
Institution (tenant root, unchanged from Module 03)
└── ExamSession (Module 04)
    └── AnswerScript                          (root: one uploaded document)
        ├── UploadJob                          (upload-attempt tracking, read-only)
        ├── ProcessingHistory                   (append-only stage-transition log)
        └── AnswerScriptPage                     (× physical page, pipeline-written)
            └── OCRJob                            (one per script; tracks the OCR run)
                └── OCRResult                       (one per page)
                    └── OCRBlock                      (× detected block)
                        └── OCRLine                     (× detected line)
                            └── OCRWord                   (× detected word)

OCRProvider (global catalog — tesseract, easyocr, paddleocr, azure_ocr,
             google_vision, aws_textract — NOT institution-owned, see ADR-028)
OCRConfiguration (tenant-scoped — institution-wide default OR per-assessment
                   override, references one OCRProvider)
```

11 tables total. See [database-standards.md](database-standards.md) for
the exact list and [database-standards.md](database-standards.md#module-05--answer-script-ocr-pipeline-tables)
for column-level conventions.

## Design decisions worth calling out (see ADR-026 through ADR-034)

- **New infrastructure, not a modification of anything** (ADR-026). MinIO
  (`app/db/storage.py`, `app/services/storage_service.py`) and Celery
  (`app/tasks/ocr_tasks.py`) go from config-only/skeleton to real, working
  code for the first time in this module — zero changes to any
  Module 01–04 file to make this happen.
- **`DocumentMetadata`/`ProcessingStatus` are columns, not tables**
  (ADR-027) — same consolidation philosophy as Module 04's ADR-021.
  `AnswerScript.status` is a single string column covering the full state
  machine (`uploading` → `uploaded` → `validating` → `validated`/
  `failed_validation` → `storing` → `stored` → `preprocessing` →
  `ocr_queued` → `ocr_running` → `ocr_complete`/`ocr_failed` →
  `structuring` → `completed`/`failed`/`cancelled`).
- **`OCRProvider` is global; `OCRConfiguration` is tenant-scoped**
  (ADR-028) — the engine catalog (`tesseract`, `easyocr`, ...) is
  system/technical data, identical across every institution; which engine
  an institution actually uses is a per-tenant choice. `OCRProvider` is
  therefore the first entity since Module 02's `Role`/`Permission` that
  does **not** compose `InstitutionOwnedMixin` — it uses the new
  `GlobalRepository`/`GlobalService` base classes
  (`app/repositories/global_repository.py`,
  `app/services/global_service.py`), which mirror
  `TenantScopedRepository`/`TenantScopedService` minus the
  `institution_id` filter.
- **Three-level result hierarchy, not four** (ADR-029) —
  `OCRResult → OCRBlock → OCRLine → OCRWord`. "Blocks" and "Paragraphs"
  from the original brief are consolidated into one `OCRBlock` level
  (`block_type` distinguishes `"text"`/`"table"`/`"image"`); Tesseract's
  own page-segmentation output doesn't reliably distinguish a block from a
  paragraph either, so a fourth level would have been unpopulated ceremony.
- **`ProcessingHistory` is distinct from `AuditLog`** (ADR-030) — the
  pipeline's own automatic stage transitions (preprocessing → ocr →
  structuring → completed) are logged here, not in Module 02's `AuditLog`
  (reserved for human-initiated actions: upload, delete, retry, cancel).
- **`structured_content` is JSON, not a relational entity set** (ADR-031)
  — same reasoning as Module 04's `EvaluationHistory.embedding_vector`:
  the exact schema of "detected sections/headings/tables" is still
  evolving, and a nested JSON tree on `AnswerScript.structured_content`
  avoids a premature five-table relational commitment. Schema documented
  below in [Structured output shape](#structured-output-shape).
- **All six providers are now real** (ADR-032, superseded by Module 12) —
  originally only Tesseract was real and the other five were
  interface-conformant stubs raising `OCRProviderNotImplementedError`.
  Module 12 replaced all five stubs with real SDK-backed implementations.
  See [Module 12: Enterprise Multi-OCR Platform](#module-12-enterprise-multi-ocr-platform)
  below for what's genuinely verified vs. credential-gated.
- **Image preprocessing is a pipeline of swappable steps** (ADR-033) —
  `app/services/image_processing/` has one file per operation (deskew,
  denoise, contrast, brightness, crop, margin-trim, resolution,
  orientation, page-split, blank-detection, rotation, PDF extraction),
  composed by `PreprocessingPipeline` (`pipeline.py`). Swapping or
  reordering steps is a one-line change to the pipeline's step list, not a
  rewrite of any individual operation.
- **Students get zero default OCR/AnswerScript access** (ADR-034) — same
  restrictive-default philosophy as Module 04's ADR-025. A student reading
  their own (or worse, another student's) raw scanned answer script before
  grading is complete is a real security bug, not a missing feature.

## Backend architecture

Every entity follows the same four-layer shape established in Module 03/04
(`endpoints/{entity}.py` → `services/{entity}_service.py` →
`repositories/{entity}_repository.py` → `models/{entity}.py}`), building on
the **unmodified** `TenantScopedRepository`/`TenantScopedService` base
classes for every tenant-owned entity, and the **new**
`GlobalRepository`/`GlobalService` for `OCRProvider` only.

### Upload endpoint

`POST /api/v1/answer-scripts` (multipart form: `exam_session_id` + `file`,
optional `allow_duplicate`) performs, synchronously, in one request:

1. Validates MIME type against `UPLOAD_ALLOWED_MIME_TYPES` (PDF, PNG, JPG,
   JPEG, TIFF, BMP, WEBP) and size against `UPLOAD_MAX_FILE_SIZE_BYTES`.
2. Computes a SHA-256 checksum and checks for a duplicate
   (`AnswerScriptRepository.find_duplicate`) — rejected with `409` unless
   `allow_duplicate=true`.
3. Verifies the parent `ExamSession` exists and belongs to the caller's
   institution (`404` otherwise).
4. Uploads the original bytes to MinIO via `StorageService` and creates the
   `AnswerScript` row with `status="stored"`.
5. Enqueues `ocr.process_answer_script` on Celery (`_enqueue_ocr_pipeline`)
   — the HTTP response returns immediately; Stages 4–8 run in the
   background.

`POST /api/v1/answer-scripts/bulk` accepts multiple files, uploading each
independently and collecting per-item errors (matching Module 04's bulk
create convention) rather than failing the whole batch on one bad file.

Additional non-CRUD endpoints: `POST /{id}/retry` (re-enqueues the pipeline
from `failed`/`cancelled`), `POST /{id}/cancel` (guards against cancelling
an already-terminal script — `409`), `GET /{id}/download` (returns a
presigned MinIO URL, never proxies the bytes through the API server).

### Background pipeline (`app/tasks/ocr_tasks.py`)

`process_answer_script_task` is a synchronous Celery task (`bind=True`,
`max_retries=3`, `soft_time_limit=300`) that bridges into the codebase's
async service layer via `asyncio.run(_run_pipeline(...))` — the simplest
option given no async worker pool is configured. This means one task
instance blocks its worker slot for the whole pipeline run (preprocessing
+ OCR + structuring), not just the CPU-bound preprocessing/OCR steps — an
accepted trade-off for this module's scale, revisit if throughput becomes
a bottleneck.

`_run_pipeline`:

1. Loads the `AnswerScript`; returns early (no-op) if it's missing or
   already `cancelled`.
2. Resolves which OCR provider to use (`_resolve_provider_code`): an
   institution-wide `OCRConfiguration` (nullable `assessment_id`) if one
   exists and is active, else the catalog's `is_default=True` provider,
   else a hardcoded `"tesseract"` fallback (always registered, always
   implemented).
3. Creates an `OCRJob` row, transitions the script through
   `preprocessing` → `ocr_running` → `structuring` → `completed`, logging
   every transition to `ProcessingHistory` via `history_service.record()`.
4. **Stage 4**: extracts page images (`extract_pages_as_images` for PDF,
   or the single uploaded image), runs each through
   `PreprocessingPipeline`, uploads each processed page to MinIO, and
   creates one `AnswerScriptPage` row per page. Blank pages
   (`is_blank_page()`) skip preprocessing entirely (writing the raw image
   through unchanged) since deskew/denoise/contrast on a blank page is
   wasted work.
5. **Stage 5**: for each non-blank page, writes the processed image to a
   temp file (the `OCRProviderAdapter` interface takes a filesystem path,
   not bytes — see below) and calls `adapter.extract()`, then persists the
   full block→line→word hierarchy via
   `OCRResultService.create_with_hierarchy()`. Blank pages get an empty
   `OCRPageResult` with no OCR call made.
6. **Stage 7**: `normalize_text()` runs against each page's raw OCR text;
   both `OCRResult.raw_text` (implicit, from the adapter) and
   `OCRResult.normalized_text` are persisted — never only one.
7. **Stage 6/8**: `build_page_structure()`/`build_structured_content()`
   assemble the final `AnswerScript.structured_content` JSON tree from the
   already-persisted `OCRResult`/`OCRBlock` rows.
8. On any exception, the script is marked `failed` with a truncated
   `failure_reason`, a `ProcessingHistory` row is written with
   `stage="failed"`, and the exception re-raises (triggering Celery's
   retry via `self.retry(exc=exc)` in the task body).

### OCR provider abstraction

`app/services/ocr/base.py` defines `OCRProviderAdapter` (one abstract
method, `extract(image_path, *, language) -> OCRPageResult`) and the
engine-agnostic result dataclasses (`OCRPageResult` → `OCRBlockResult` →
`OCRLineResult` → `OCRWordResult`, each carrying a `BoundingBox` and a
0–100 `confidence`). Every engine — real or stub — returns the exact same
shape, which is what lets the persistence layer
(`OCRResultService.create_with_hierarchy`) and the pipeline stay completely
engine-agnostic.

`app/services/ocr/providers/tesseract_provider.py` is the one real
implementation, wrapping `pytesseract`/the system Tesseract binary
(`Settings.TESSERACT_CMD`, or `PATH` if unset). It calls
`pytesseract.image_to_data()` (word-level TSV output), groups words into
lines/blocks by Tesseract's own `block_num`/`par_num`/`line_num` indices,
and best-effort detects page rotation via `pytesseract.image_to_osd()`
(any `TesseractError` — common on sparse/blank images — is treated as
"assume unrotated," not surfaced as a pipeline failure).

#### Adding a new OCR provider

1. Implement `OCRProviderAdapter.extract()` in the existing stub file
   (e.g. `app/services/ocr/providers/easyocr_provider.py`), replacing the
   `raise OCRProviderNotImplementedError(...)` body with a real call.
2. Set `is_implemented = True` on the class.
3. Update the seeded `OCRProvider.is_implemented` row (migration or
   admin `PATCH /ocr-providers/{id}`) — `OCRProviderService.update()`
   already enforces `is_enabled=True requires is_implemented=True`.

No router, model, schema, or migration change is needed — the registry
(`app/services/ocr/registry.py`) and the `OCRProvider` catalog both already
carry all six provider codes.

### Image preprocessing pipeline

`app/services/image_processing/pipeline.py`'s `PreprocessingPipeline`
composes a configurable, ordered list of named steps (default: deskew,
denoise, contrast, brightness, crop-to-content via margin-trim,
resolution-normalize, orientation-correct — 7 of the 12 total available
operations run by default; `page_split`/`blank_detection`/`pdf_extraction`
are invoked directly by the pipeline task, not as pipeline *steps*, since
they operate at the document level rather than per-page). Each step is a
pure(-ish) function taking and returning an `np.ndarray` — `deskew(image,
angle=...)`, `denoise(image)`, etc. — independently swappable and testable
without a real image file.

### RBAC

20 new `PermissionCode` members (263 total): `answer_scripts`
create/read/update/delete/retry/cancel, `answer_script_pages` read-only,
`upload_jobs` create/read-only, `ocr_providers` read/update (no
create/delete — rows are seeded, not client-created),
`ocr_configurations` full CRUD, `ocr_jobs` create/read/cancel,
`ocr_results` read-only, `processing_history` read-only.

| Role | Grant shape |
|---|---|
| `super_admin` | Every permission (automatic, unchanged mechanism from Module 02). |
| `institution_admin` | Full CRUD on everything in scope, including `ocr_providers:update` and full `ocr_configurations` CRUD. |
| `teacher` | Upload/retry/cancel `answer_scripts`, read everything else (pages, jobs, results, history) — no `ocr_providers`/`ocr_configurations` write access (institution-level OCR engine choice is an admin concern). |
| `student` | **Zero** default grants — see ADR-034 above. |

### Audit logging

7 new `AuditAction` entries (38 total): `ANSWER_SCRIPT_UPLOADED`,
`ANSWER_SCRIPT_DELETED`, `ANSWER_SCRIPT_RETRIED`, `ANSWER_SCRIPT_CANCELLED`,
`OCR_JOB_EXECUTED`, `OCR_PROCESSING_COMPLETED`, `OCR_PROCESSING_FAILED`.
Human-initiated actions (upload/delete/retry/cancel) go through the
existing `AuditService`, same as every prior module; automatic pipeline
stage transitions go through `ProcessingHistory` instead (see ADR-030).

## Structured output shape

`AnswerScript.structured_content` (plain `JSON` column, ADR-031):

```json
{
  "schema_version": 1,
  "page_count": 2,
  "pages": [
    {
      "page_number": 1,
      "detected_questions": [
        { "marker_text": "Q1", "question_number": "1", "char_offset": 0 }
      ],
      "blocks": [
        {
          "block_type": "text",
          "reading_order": 0,
          "bbox": { "left": 10, "top": 20, "width": 500, "height": 40 },
          "confidence": 92.4,
          "lines": [
            { "text": "Q1) What is...", "reading_order": 0, "words": ["Q1)", "What", "is", "..."] }
          ]
        }
      ]
    }
  ]
}
```

`detected_questions` is a **best-effort, non-evaluative** heuristic
(`document_structure_service.py::detect_question_markers`, a regex
matching common "Q1"/"Question 2:"/"3)"-style numbering) — it marks where a
question boundary *appears* to start, nothing more. False positives are
expected and acceptable; Module 06 still needs to confirm boundaries
against the actual `Question` bank content before trusting them for
anything evaluative.

## Database

11 new tables, created by `0008_create_ocr_pipeline_tables.py` (generated
the same way as Modules 03/04's table migrations — Alembic's own
autogenerate-diff engine against an in-memory SQLite baseline of the
pre-Module-05 schema); `0009_seed_ocr_pipeline_permissions.py` seeds the 20
new `PermissionCode` rows (idempotent, same defensive pattern as `0005`/
`0007`) **and** the 6 `OCRProvider` catalog rows (`tesseract` seeded
`is_enabled=True, is_implemented=True, is_default=True`; the other five
`is_enabled=False, is_implemented=False`). Migration chain: `0001` → ... →
`0009`. See [database-standards.md](database-standards.md) for the full
table list.

## Frontend

Zero new shared infrastructure was needed for 6 of the 10 screens — Module
03/04's `DataTable`/`FormDialog`/`ConfirmDialog`/`PaginationControls`/
`SearchInput`/`PageHeader`/`FormField`/hooks were reused unchanged. The
other 4 screens (viewers) are read-only detail views with no CRUD form.

| Screen | Route | Notes |
|---|---|---|
| Answer Script Upload Dashboard | `/dashboard/answer-scripts` | Drag & drop + file-picker upload, list/search/paginate. |
| Upload Queue | `/dashboard/upload-queue` | `UploadJob` progress/status tracking. |
| OCR Status Dashboard | `/dashboard/ocr-status` | `OCRJob` list, links into script/job detail. |
| Answer Script Viewer | `/dashboard/answer-scripts/:id` | Detail + page list + retry/cancel/download actions. |
| Page Viewer | `/dashboard/answer-scripts/:scriptId/pages/:pageId` | One page's image + link to its OCR result. |
| OCR Text Viewer | `/dashboard/ocr-results/:id` | Normalized text + block/line/word tree for one page. |
| Processing History | `/dashboard/answer-scripts/:scriptId/history` | Read-only `ProcessingHistory` timeline for one script. |
| OCR Job Details | `/dashboard/ocr-jobs/:id` | One job's status/provider/timing detail. |
| OCR Provider Management | `/dashboard/ocr-providers` | Admin-only enable/disable/set-default toggles. |
| OCR Configuration | `/dashboard/ocr-configurations` | Institution-wide/per-assessment OCR settings CRUD. |

`types/ocr.ts` mirrors every backend Pydantic schema field-for-field (same
`Decimal → string` on Read / `number` on Create-Update convention as
`types/assessment.ts`); 8 new `api/*.ts` modules — `ocrConfigurations.ts`
uses the standard `createCrudApi` factory, the other 7 are hand-written
because their routers aren't uniform CRUD (multipart upload, no
`PATCH`/`DELETE`, or a nested-tree endpoint).

Routes are gated with `PermissionGuard` exactly like Module 03/04, lazy-
loaded/code-split the same way, and `Sidebar.tsx` filters its 5 new
top-level nav entries (Answer Scripts, Upload Queue, OCR Status, OCR
Providers, OCR Configurations) by the current user's permissions — the 5
detail/viewer screens are reachable only by navigating from a list screen,
not given their own sidebar entry, matching Module 04's
`QuestionViewerPage`/`QuestionEditorPage` precedent.

## Testing

Backend: 944 tests, 97.54% coverage — including a real, non-mocked
Tesseract OCR pass (`tests/test_ocr_providers.py`,
`tests/test_ocr_tasks.py`) against synthetic images, exercised through the
actual Celery pipeline orchestration function (`_run_pipeline`) against an
in-memory SQLite session. Frontend: 407 tests (60 files), 96.42% coverage.
See [TESTING_STATUS.md](../TESTING_STATUS.md) for the itemized breakdown.

## Module 12: Enterprise Multi-OCR Platform

Extends the six-provider catalog from "one real engine + five stubs"
(ADR-032) to six real, SDK-backed implementations, entirely additively —
no existing entity was redesigned, no existing API/DB contract broke, and
`OCRProviderAdapter.extract()` (the one abstract method) is unchanged, so
every pre-Module-12 caller keeps working untouched.

### Provider status (what's genuinely verified vs. credential-gated)

Updated by the **Surya/docTR/TrOCR Isolated-Runtime milestone**'s
real-infrastructure verification pass (superseding the Six-Provider OCR
milestone's table below) — every row reflects an actual command/API call
run during that milestone, not documentation carried over unverified. See
[Isolated OCR Runtime Bridge](#isolated-ocr-runtime-bridge-surya--doctr--trocr--paddleocr-milestone)
further down for the full architecture and evidence.

| Provider | Code | Status | What's needed to activate |
|---|---|---|---|
| Tesseract | `tesseract` | ✅ **VERIFIED WORKING** — real extraction via the actual app code path, 95.4% confidence, correct text | Nothing — already the default |
| EasyOCR | `easyocr` | ✅ **VERIFIED WORKING** (CPU) — real extraction, 77-85% confidence depending on sample. GPU hardware present (RTX 4050) but the installed `torch` build is CPU-only | Nothing for CPU; a CUDA-enabled `torch` wheel to use the GPU |
| PaddleOCR | `paddleocr` | ✅ **VERIFIED WORKING** — now runs through the isolated `.venv-paddleocr` runtime bridge (invoked as a subprocess from the main backend process); real end-to-end extraction, 99.1-99.8% confidence. Previously ENVIRONMENT-GATED (Windows Smart App Control blocked the DLL load when imported *in-process*) — the bridge never asks the main process to load paddle's DLLs, so the block never triggers; Smart App Control itself was never touched | Nothing — bridge ships with the repo; create `.venv-paddleocr` per [below](#isolated-ocr-runtime-bridge-surya--doctr--trocr--paddleocr-milestone) |
| Surya | `surya` | ✅ **VERIFIED WORKING** — isolated `.venv-surya` runtime bridge, pinned to `surya-ocr==0.13.1` (see below for why); real end-to-end extraction, 95-99.9% per-line confidence, 100% correct text on the representative sample | Create `.venv-surya`, install `surya-ocr==0.13.1` + `transformers==4.46.3` |
| docTR | `doctr` | ✅ **VERIFIED WORKING** — isolated `.venv-doctr` runtime bridge (`python-doctr[torch]`); real end-to-end extraction, 90-99.98% per-word confidence | Create `.venv-doctr`, install `python-doctr[torch]` |
| TrOCR (Handwritten) | `trocr_handwritten` | ✅ **VERIFIED WORKING** — isolated `.venv-trocr` runtime bridge running `microsoft/trocr-base-handwritten` behind a real EasyOCR-detect → crop → recognize pipeline; real end-to-end extraction, 94.6-99.97% confidence | Create `.venv-trocr`, install `torch` + `transformers==4.46.3` + `sentencepiece` |
| Azure Document Intelligence | `azure_ocr` | Real SDK code, unit-tested against deterministic fakes; **not yet run against a live Azure resource** (no credentials in this environment) | `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` + `AZURE_DOCUMENT_INTELLIGENCE_API_KEY` |
| Google Cloud Vision | `google_vision` | Real service-account credentials configured and **authenticate successfully**; the Cloud Vision API itself is disabled on the associated GCP project (403 `SERVICE_DISABLED`) — authentication succeeding is *not* enough to call this VERIFIED, since no real OCR response has ever been returned | Enable `vision.googleapis.com` on the project (billing/console action) |
| AWS Textract | `aws_textract` | Real SDK code, unit-tested against deterministic fakes; **not yet run against a live AWS account** (no credentials anywhere in this environment) | `AWS_TEXTRACT_REGION` + `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (or the standard boto3 credential chain) |

All six local providers are genuinely operational as of this milestone —
see the [six-provider real E2E result](#real-verification-performed-isolated-runtime-bridge)
further down for the live Celery/Postgres/MinIO proof.

`is_implemented=True` in the `OCRProvider` catalog means *real code exists*,
not *this deployment is configured*. The separate `configured`/`ready`
fields on `HealthCheckResult` (below) tell you the latter.

### The 19-method rich interface

`OCRProviderAdapter` (`app/services/ocr/base.py`) grew from one abstract
method to a much richer surface — `initialize()`, `shutdown()`,
`health_check()`, `extract_document()`, `extract_pages()`,
`extract_blocks()`, `extract_paragraphs()`, `extract_lines()`,
`extract_words()`, `extract_tables()`, `extract_layout()`,
`extract_handwriting()`, `extract_images()`, `confidence_score()`,
`supported_languages()`, `provider_name()`, `provider_version()`,
`processing_time()`, `capabilities()` — all added as **concrete methods
with sensible defaults**, not new abstract requirements. `extract()` is
still the only method a provider must implement; every pre-Module-12
provider and caller that only ever calls `.extract()` is unaffected.

New standalone result shapes (`app/services/ocr/models.py`, additive to
`base.py`'s existing `OCRPageResult` tree): `OCRParagraphResult`,
`OCRTableResult`/`OCRTableCell`, `OCRLayoutResult`/`OCRLayoutRegion`,
`OCRImageRegion`, `OCRDocumentResult`, `ProviderMetadata`,
`HealthCheckResult`, `ProviderCapabilities`. None of these are persisted —
they back the richer read-side methods above; the persisted hierarchy is
still exactly `OCRResult → OCRBlock → OCRLine → OCRWord` (ADR-029 stands).

### Health check

`GET /api/v1/ocr-providers/{id}/health` runs a real, on-demand check
against the actual adapter (never cached, never persisted) and returns
`HealthCheckResult`: `installed`, `version`, `configured`, `authenticated`,
`connectivity`, `dependencies_ok`, `gpu_available`, `ready`, `detail`. The
OCR Provider Management admin page (`/dashboard/ocr-providers`) has a
"Check" button per row that calls this live.

### Benchmark

`POST /api/v1/ocr-providers/benchmark` (multipart: `file`, optional
`language`/`provider_codes`/`reference_text`) runs one page image through
every requested provider (default: all registered) and reports
`provider_version`, `processing_time_seconds`, `average_confidence`,
`character_count`/`word_count`, `throughput_chars_per_second`,
`cpu_percent`/`memory_delta_mb` (via `psutil`), `gpu_available`, and — only
if `reference_text` is supplied — `word_accuracy`/`character_accuracy`.
Nothing is persisted (`OCRBenchmarkService`, `app/services/ocr_benchmark_service.py`).
Gated behind `ocr_providers:update` (not `:read`), since it genuinely
executes every engine, including live cloud-API calls for credential-gated
providers. The same admin page has a benchmark card that drives this.

### Preprocessing additions

Four new steps added to `app/services/image_processing/`
(`perspective.py`, `adaptive_threshold.py`, `sharpen.py`,
`background_clean.py`), registered in `pipeline.py`'s `_STEP_FUNCTIONS` but
**not** added to `DEFAULT_STEP_ORDER` — they're selectable via
`OCRConfiguration.preprocessing_steps` without changing the existing
pipeline's default behavior.

### Provider selection: `OCR_PROVIDER` env var

An operator-level override, checked first in `_resolve_provider_code`
(`app/tasks/ocr_tasks.py`), ahead of the institution's `OCRConfiguration`/
default-provider resolution — set `OCR_PROVIDER=azure_ocr` (etc.) to force
one engine for testing, incident response, or a benchmark run, with no
code or DB change.

### Configuration reference

All provider-specific settings are env vars (`app/core/config.py`), not DB
columns — credentials/endpoints are infra-level secrets, and `OCRProvider`
is a global system catalog (ADR-028), not a place to store per-tenant keys.

```text
OCR_PROVIDER                              # optional override, see above
OCR_EASYOCR_GPU / _LANGUAGES / _MODEL_DIR
OCR_PADDLEOCR_GPU / _LANGUAGE / _DET_THRESHOLD / _REC_THRESHOLD
GOOGLE_VISION_CREDENTIALS_PATH / _PROJECT_ID
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT / _API_KEY
AWS_TEXTRACT_REGION / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
```

### Database changes (Module 12)

`0014_extend_ocr_provider_metadata.py` (additive only): adds
`provider_version`/`processing_time_ms`/`image_resolution`/
`raw_response_reference` (all nullable) to `ocr_results`, and updates the
`ocr_providers` seed data's `is_implemented` to `True` for the five
previously-stub providers (`is_enabled`/`is_default` are left `False` —
an administrator must still explicitly enable each one).

### Deployment note: Python version

This project's Docker image (`backend/Dockerfile`) targets Python 3.13.
`paddlepaddle` publishes no Python 3.14 wheel as of writing, so a native
Windows dev venv on 3.14 cannot install the `paddleocr` extra — this is a
local-dev-only gap, not a production one. Install it via
`pip install -e ".[paddleocr]"` (declared as an optional extra in
`pyproject.toml` for exactly this reason).

### Known issues: PaddleOCR + Windows

Three genuine issues have been found while verifying PaddleOCR on
Windows — worth knowing about for any future upgrade:

1. **DLL load order**: paddlepaddle and torch (an indirect paddleocr 3.x
   dependency) each ship a same-named native DLL; whichever loads into the
   process first wins. `paddleocr_provider.py` always imports `paddleocr`
   before `paddle` for this reason — and does so via
   `importlib.import_module()`, not plain `import` statements, since
   ruff's isort auto-fixer will otherwise silently alphabetize (and
   therefore break) that order on `ruff check --fix`.
2. **`enable_mkldnn=False` is required** on this CPU build — with MKL-DNN
   left on (paddlepaddle's default), real inference raises
   `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
   [...]` inside paddle's own oneDNN executor. This is a paddlepaddle
   3.3.1 CPU-inference bug, not something under this codebase's control
   beyond disabling the affected acceleration path.
3. **Windows Smart App Control could block `.venv-paddleocr`'s `torch` DLL
   when imported in-process** (found during the Six-Provider OCR
   milestone) — a hard `OSError: [WinError 4551] An Application Control
   policy has blocked this file` on `torch/lib/c10.dll` when the *main
   backend process* imported `paddleocr`/`torch` directly, even though the
   byte-identical package loaded without issue when the main venv's own
   process imported it (confirmed via
   `HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy
   \VerifiedAndReputablePolicyState` = `1`, i.e. Smart App Control
   enabled). **Resolved in the Surya/docTR/TrOCR Isolated-Runtime
   milestone** without touching Smart App Control at all: `PaddleOCRProvider`
   now invokes `.venv-paddleocr` as a subprocess (the same isolated-runtime
   bridge built for Surya/docTR/TrOCR — see
   [below](#isolated-ocr-runtime-bridge-surya--doctr--trocr--paddleocr-milestone))
   instead of importing `paddleocr` into the main process. Smart App
   Control's policy attaches per-process — the isolated `.venv-paddleocr`
   process loading its own DLLs was never the operation being blocked;
   only the main process attempting the same import was. **Do not disable
   Smart App Control** — it was never the right fix, and still isn't.

Issues 1–2 are Windows-native-library quirks and not expected to reproduce
in Linux Docker; issue 3's underlying Smart App Control behavior is
Windows-specific by definition, but the isolated-runtime-bridge fix
applies equally on Linux (any process-boundary reason to isolate a heavy
ML dependency benefits from the same pattern).

### Provider fallback strategy (Six-Provider OCR milestone, Phase 12)

`app/tasks/ocr_tasks.py::_run_pipeline` now falls back to `tesseract`
(always registered, always implemented, no credentials) **once** per job
if the resolved primary provider raises a provider-level failure —
`OCRDependencyMissingError`/`OCRProviderConfigurationError`/
`OCRProviderAuthenticationError`/`OCRProviderConnectivityError`/
`OCRProviderTimeoutError`/`OCRProviderRateLimitError`. Content-level
failures (`OCRUnsupportedFormatError`/`OCRCorruptedDocumentError`) never
trigger a fallback, since switching providers can't fix a corrupt or
unsupported input.

The fallback is always visible, never silent: `OCRJob` gained two nullable
columns (`0016_ocr_job_provider_fallback.py`) —
`requested_ocr_provider_id` (only populated when a fallback actually
happened; `NULL` is the common "ran exactly as requested" case) and
`fallback_reason` (the original provider's real error message). The OCR
Job Details page (`/dashboard/ocr-jobs/:id`) renders a visible "Provider
Fallback" banner whenever `requested_ocr_provider_id` is set. At most one
fallback attempt happens per job (never a cascading chain through all six
providers) — if the fallback target itself also fails, or the primary
provider *was* already the fallback target, the original failure
propagates and retries via Celery's own `self.retry()` exactly as before.

This is a direct, measured response to a genuine finding from this same
milestone's real-database inspection: the seeded `ocr_providers` catalog's
`is_default=True` row is `azure_ocr`, which has no credentials configured
in this environment — meaning any fresh institution with no explicit
`OCRConfiguration` override would previously have failed OCR processing
entirely by default. The fallback strategy makes that failure mode
recoverable instead of fatal.

### Celery/Redis real-infrastructure verification (Six-Provider OCR milestone, Phase 18)

A previous report noted "Celery task code exists and is tested but a live
worker had not been conclusively exercised" and flagged "Redis-unavailable
retry behavior" as needing future hardening. Both were closed for real
this milestone:

- **Root cause of the flaky Redis behavior**: this dev machine's `.env`
  pointed `REDIS_PORT` at `6380`, but the actual running `redis-server`
  process listens on the default `6379` — a plain configuration mismatch,
  now fixed. Separately, that running Redis instance turned out to be
  version **3.0.504** (the historical Windows-native "Redis on Windows"
  port, last updated circa 2015) — pre-dating RESP3 entirely, while modern
  `redis-py`/`kombu` attempt a RESP3 `HELLO` handshake on connect by
  default and hard-fail against any Redis older than 6.0.
- **Fix**: `app/tasks/redis_resp2_transport.py` registers a `redis2://`
  kombu transport + Celery result-backend alias that pins every
  connection to RESP2 (and disables redis-py 8.x's Enterprise-only
  "maintenance notifications" feature, which otherwise hard-requires
  RESP3). `Settings.redis_uri_for_db()` uses this scheme for
  `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`; `Settings.REDIS_URI` (the
  app's own direct Redis client, used for rate limiting/readiness probes)
  uses plain `redis-py`'s `?protocol=2` query-string support instead,
  since kombu's URL parser and real `redis-py`'s handle that parameter
  differently.
- **Real, live verification performed**: started an actual `celery -A
  app.tasks.celery_app worker` process against the real local Redis
  instance (not a test double) — it connected successfully and registered
  all four real tasks. Then ran a genuine Upload → Celery → OCR Provider →
  Database flow end to end: a real multi-page PDF, uploaded to a real
  local MinIO instance, processed by the real live worker through the
  real Tesseract provider, with the final `AnswerScript.structured_content`
  and `OCRJob` rows verified directly in the real Postgres database. This
  is what surfaced both the orientation-detection bug and the Tesseract
  PSM bug documented below — genuine defects a synthetic/mocked test would
  not have caught.

### Known issues: preprocessing/OCR interaction bugs found via real verification (Six-Provider OCR milestone)

Two genuine, previously-undetected bugs were found (and fixed) via the
live end-to-end run described above — both are documented in the
affected functions' own docstrings, summarized here for visibility:

1. **`detect_orientation()` could flip a correctly-oriented page upside
   down** (`app/services/image_processing/orientation.py`). Row-sum
   *variance* is mathematically identical for an image and its
   180-degree rotation (reversing row order doesn't change their
   distribution), so naively comparing all four candidate rotations made
   the 0-vs-180 choice come down to floating-point noise — confirmed to
   actually invert a realistic multi-line page. Fixed: variance now only
   decides *upright-group vs. sideways-group*, always resolving to the
   group's canonical representative (`0` or `90`), never inverting
   already-correct content. Genuinely upside-down scans remain
   undetectable by this heuristic (a pre-existing, now-explicitly-
   documented limitation, not a regression).
2. **Tesseract's default page-segmentation mode (PSM 3) can find *zero*
   text on an extreme-aspect-ratio strip** (`tesseract_provider.py`) —
   exactly what this module's own `trim_margins` preprocessing step
   produces for a single-line page (confirmed: a ~14:1 aspect-ratio
   175×2480px crop returned an empty string under PSM 3 while an
   almost-identical sibling page didn't). Fixed: `TesseractProvider`
   now detects an aspect ratio ≥ 5:1 and substitutes PSM 6 ("assume a
   single uniform block of text") automatically, unless a PSM was
   explicitly configured. Ordinary page-shaped images are unaffected.

### Quality gate checklist

- [x] All six providers function independently (each instantiable via the
      registry with no code change elsewhere).
- [x] Provider switching needs no code change (`OCR_PROVIDER` env var or
      `OCRConfiguration`/catalog `is_default`).
- [x] Provider fallback strategy implemented, tested, and visible (never
      silent) — see above.
- [x] Standard output identical across providers (`OCRPageResult` shape).
- [x] Existing OCR workflow intact (`_run_pipeline`'s shape unchanged;
      only additive metadata capture + fallback logic added).
- [x] Existing APIs backward compatible (no endpoint removed/renamed;
      `OCRJobRead`/`OCRResultRead` gained optional fields only).
- [x] DB schema stable except approved additive changes
      (`0014_extend_ocr_provider_metadata.py`,
      `0016_ocr_job_provider_fallback.py`).
- [x] Real Celery worker verified against real Redis, real MinIO, and a
      real multi-page PDF end to end — see above.
- [x] Full backend + frontend regression suites re-run against the
      current tree — see [TESTING_STATUS.md](../TESTING_STATUS.md) for
      the latest confirmed numbers.

## OCR Ensemble & Fusion (Safe Final OCR Ensemble milestone)

Opt-in, off by default (`OCRConfiguration.is_ensemble_enabled=False` for
every existing institution) — running the single-provider path exactly as
documented above remains the default and fully unaffected behavior.

### Architecture

```text
Page image
    |
OCR Ensemble Orchestrator (app.services.ocr.ensemble.run_ensemble)
    |
    +-- provider 1 (e.g. tesseract) --> success/failure, adapter.shutdown()
    +-- provider 2 (e.g. easyocr)   --> success/failure, adapter.shutdown()
    +-- ... sequential, never concurrent (GPU-memory safety) ...
    |
OCR Fusion Engine (app.services.ocr.fusion.fuse_page_candidates)
    |
Consensus OCRPageResult --> OCRResultService.create_with_hierarchy()
                             (is_ensemble_result=True)
    |
    +-- OCRResult (fused text, same shape every non-ensemble row has)
    +-- OCRProviderCandidate x N (every contributing provider's raw output, never discarded)
```

Enable per institution via `PATCH /ocr-configurations/{id}` (or `POST`
on create): `is_ensemble_enabled=true`, optionally
`ensemble_provider_codes=["tesseract", "easyocr", ...]`. Omitting
`ensemble_provider_codes` runs every registered, enabled **local**
provider (`tesseract`/`easyocr`/`paddleocr`/`doctr`/`surya`/
`trocr_handwritten`) — cloud providers are never a silent default (an
institution flipping one boolean must never unexpectedly start incurring
cloud API costs); list a cloud code explicitly to include it.

### Orchestrator: sequential execution, partial-failure tolerance

`run_ensemble()` calls each requested provider's `adapter.extract()` one
at a time, never concurrently — this machine's RTX 4050 has 6 GB VRAM,
not enough to hold every GPU-capable engine loaded simultaneously.
`adapter.shutdown()` runs after every provider (success or failure) to
release GPU/CPU model memory before the next one loads. One provider's
failure is recorded as a `status="failed"` candidate and never aborts the
run — every other requested provider still executes, and fusion proceeds
with whatever succeeded (an empty, zero-confidence result only if *every*
requested provider failed).

### Fusion Engine: real, deterministic, line-level consensus

`fuse_page_candidates()` — pure function, no I/O, fully unit-tested
(`tests/test_ocr_fusion.py`, 9 tests):

1. The candidate with the most detected lines becomes the alignment
   reference (maximizes resolution).
2. Every other candidate's lines are matched to each reference line by
   **vertical bounding-box overlap** (IoU ≥ 0.5) — geometric alignment,
   not text-similarity-based, since two providers segmenting the same
   physical line always produce overlapping boxes even when their text
   disagrees completely (the exact case this engine exists to catch).
3. Among aligned candidates for a line, the text is chosen from whichever
   has the highest `confidence × provider reliability weight` —
   deterministic, never "first" or "longest."
4. If aligned candidates' texts fall below an 85% normalized-similarity
   threshold (`difflib.SequenceMatcher`), it's recorded as a genuine
   **disagreement region** (every candidate's text preserved, plus which
   one was chosen and why) — never silently discarded.
5. Final confidence is a length-weighted average across fused lines.

**Granularity, stated honestly**: this is real line-level fusion, not
word/sub-word spatial reconstruction — several engines
(EasyOCR/PaddleOCR) synthesize word-level bounding boxes from their line
box rather than measuring them, so word-level spatial fusion across
providers would have required fabricating precision those engines'
own outputs don't genuinely carry.

Provider weights (`DEFAULT_PROVIDER_WEIGHTS`) are reasonable, documented
starting defaults, **not measured accuracy figures** — configurable per
call, intended to be tuned from real `OCRBenchmarkService` results over
time.

### Persistence: nothing is discarded

`OCRResult` gains `is_ensemble_result`/`contributing_provider_codes`/
`disagreement_regions` (all nullable/defaulted — every pre-Ensemble-Mode
row stays valid as `is_ensemble_result=False`). The new
`OCRProviderCandidate` table (migration `0017_ocr_ensemble_fusion.py`)
holds one row per (page, provider) pair — `status`, `raw_text`,
`confidence`, a full block/line/word JSON tree, and (for failures) the
real error message — so every contributing engine's actual output is
auditable after fusion, never overwritten or dropped.

### Real verification performed

A live Celery worker (connected to the real local Redis via the
`redis2://` RESP2 transport) processed a genuine multi-line page image
through real Tesseract + real EasyOCR, fused by the real Fusion Engine,
against the real local Postgres database and real local MinIO — verified
directly via SQL: `OCRResult.is_ensemble_result=True`,
`contributing_provider_codes=["easyocr","tesseract"]`, two
`OCRProviderCandidate` rows (`tesseract` confidence 95.54,
`easyocr` confidence 84.42), correctly fused four-line consensus text
matching the source image exactly.

### Isolated OCR Runtime Bridge (Surya / docTR / TrOCR / PaddleOCR milestone)

The prior milestone found real `pip install --dry-run` conflicts for
`surya-ocr` (would downgrade `pillow`/`opencv-python-headless` in the main
venv) and `python-doctr` (would install non-headless `opencv-python`
alongside the existing `opencv-python-headless`, a dual-`cv2`-namespace
conflict) and deferred both rather than force them into the stable venv.
This milestone builds the isolated-runtime architecture that resolves
that tension — **and turns out to also fix PaddleOCR's unrelated Smart
App Control problem for free**, since it's the same underlying pattern.

#### Architecture

```text
Main backend process (.venv, Python 3.14)
        |
Provider adapter (SuryaOCRAdapter / DocTROCRAdapter /
                  TrOCRHandwrittenAdapter / PaddleOCRProvider)
        |
app.services.ocr.isolated_runtime.invoke_isolated_runtime()
        |
        | subprocess: <isolated-venv>/Scripts/python.exe <runner>.py <request.json> <response.json>
        v
Isolated venv (.venv-surya / .venv-doctr / .venv-trocr / .venv-paddleocr,
               each a separate Python 3.13 install, next to each other
               under backend/)
        |
Runner script (app/services/ocr/isolated_runners/*.py) — real inference,
never imported by the main venv, writes its JSON response to a file
        |
Normalized OCRPageResult back in the main process
```

**Protocol, deliberately file-based, not stdout-JSON**: the caller writes
a request to a temp JSON file and passes both that path and a response
path as argv to the runner. The runner writes its response to the second
path explicitly. This means a stray `print()`/progress-bar/warning from
any of these libraries (all of which produce plenty of both) can never
corrupt the protocol — only the response *file*, written once at the end,
is ever parsed. Real stdout/stderr are still captured for diagnostics and
included verbatim in the raised exception on failure.

**Failure handling** (`app.services.ocr.exceptions`): `OCRIsolatedRuntimeMissingError`
(interpreter/script not found), `OCRIsolatedRuntimeTimeoutError`,
`OCRIsolatedRuntimeCrashError` (non-zero exit), `OCRIsolatedRuntimeMalformedResponseError`
(exited 0 but no/invalid response file), `OCRIsolatedRuntimeInferenceError`
(a well-formed `success: false` response — a caught error inside the
runner, not a crash). One provider's bridge failure becomes an ensemble
`status="failed"` candidate exactly like any in-process provider failure
— `run_ensemble()` needed zero changes to support bridged providers.

#### Surya: why it's pinned to `0.13.1`, not the latest `0.22.1`

Installing the latest `surya-ocr` (`0.22.1`) and attempting real
inference produced a genuine, reproducible finding: its current
`RecognitionPredictor` is a "Foundation model" rewrite whose only two
inference backends both require an external server process this machine
doesn't have —

- `vllm` backend: `SpawnError: docker binary not found` (confirmed by
  real attempted inference, not assumption — Docker is not installed).
- `llamacpp` backend: spawns a native `llama-server` binary via
  `shutil.which()`, with install instructions documented only for
  macOS/Linux (`brew install llama.cpp`) — no Windows path offered by the
  library itself.

Neither Docker nor a manually-downloaded third-party server binary was
installed to force this — both are real infrastructure changes beyond
what this milestone's "safe, incremental provider addition" scope calls
for. `surya-ocr==0.13.1` is the last release line with the classic, fully
local, pure-PyTorch `DetectionPredictor`/`RecognitionPredictor` API (no
server process) — real, genuine in-process inference, no Docker. Its
default `transformers` resolution (`4.57.6`) hit a separate real bug
(`KeyError: 'encoder'` inside `transformers`' `to_diff_dict()` calling
`SuryaOCRConfig.__init__()`, a version-incompatibility between that very
new `transformers` release and `surya`'s own config class) — pinned to
`transformers==4.46.3` in `.venv-surya` to resolve it, confirmed working
by real inference afterward.

#### TrOCR: the required line-detection/cropping pipeline

`microsoft/trocr-base-handwritten` is a line-level handwriting
recognizer, not a page-level OCR engine — whole-page-to-TrOCR was
explicitly out of scope. `TrOCRHandwrittenAdapter.extract()` implements
the real pipeline this requires:

1. **Detect**: reuses the already-verified, already-in-process
   `EasyOCRProvider` purely as a line detector — its geometry is kept,
   its own recognized text is discarded (TrOCR re-recognizes each region).
2. **Crop**: each detected line's box (+4px padding) is cropped from the
   original page image into its own temp PNG.
3. **Recognize**: all crops for a page are sent to `.venv-trocr` in one
   subprocess call; the runner runs real `VisionEncoderDecoderModel.generate()`
   per crop.
4. **Reconstruct**: recognized text is reattached to each line's original
   detected bounding box, in the detector's own reading order.

TrOCR's `generate()` has no native calibrated confidence score. Rather
than fabricate one, the runner computes a genuine (explicitly labelled as
a *proxy*, not a native metric) per-token softmax-probability average
from the model's own real output distribution — a real, reproducible
measurement, just not one TrOCR itself reports.

`.venv-trocr`'s default `pip install transformers` resolved to `5.14.1`,
which failed to load `TrOCRProcessor.from_pretrained(...)`'s tokenizer
(`ValueError: Couldn't instantiate the backend tokenizer ... need to have
sentencepiece or tiktoken installed`) even with `sentencepiece` genuinely
installed — a real, reproducible incompatibility between that release and
this checkpoint's tokenizer files. Pinned to `transformers==4.46.3` (the
same version that resolved Surya's issue), confirmed working by real
inference afterward.

#### Real verification performed (isolated-runtime bridge)

Every adapter has both a mocked unit-test layer (normalization,
`success: false` handling, missing-venv health check) and a real
integration test (skipped, not failed, when the corresponding isolated
venv doesn't exist on a machine — `tests/test_ocr_provider_{surya,doctr,
trocr,paddleocr_bridge}.py`), plus `tests/test_ocr_isolated_runtime.py`
(8 tests covering the bridge itself: missing interpreter, missing script,
timeout, crash, malformed response, stray-stdout-noise tolerance) and
`tests/test_ocr_ensemble.py` (7 tests covering the orchestrator's control
flow with fake adapters). All real integration tests genuinely passed on
this machine.

A representative 4-line printed test image was run through all six local
providers sequentially via `run_ensemble()`, then through a real live
Celery worker end to end (real Postgres, real MinIO, real Redis via the
`redis2://` transport):

| Provider | Status | Confidence | Processing time |
|---|---|---|---|
| tesseract | success | 94.90% | 797ms |
| easyocr | success | 77.46% | 9,132ms |
| paddleocr | success | 99.77% | 23,429ms |
| doctr | success | 90.08% | 7,056ms |
| surya | success | 98.64% | 11,617ms |
| trocr_handwritten | success | 96.13% | 24,549ms |

All six succeeded, all six contributed to fusion, **zero disagreement
regions** (the providers' individual recognition errors — e.g. docTR's
"rundamental orinciple" for "fundamental principle", PaddleOCR's "E
eguals" for "F equals" — were each corrected by the fusion engine
selecting a higher-`confidence × weight` line from a different provider),
fused confidence **99.95%**, fused text exactly matching the source
image. Verified directly via SQL against the real `OCRResult`/
`OCRProviderCandidate` rows: `is_ensemble_result=True`,
`contributing_provider_codes` containing all six codes, six
`OCRProviderCandidate` rows all `status="success"`.

**Honest performance note**: each isolated-provider call currently pays a
full subprocess-plus-model-load cost (there is no persistent isolated
server process kept warm between calls) — the processing times above
include that cost. This is an acceptable tradeoff for correctness/safety
over raw throughput this milestone (the "minimum reusable bridge"
explicitly called for), not a claim that it's already optimized for
production request latency.

#### Provider registration (migration `0018`)

`0018_seed_isolated_local_ocr_providers.py` (additive, idempotent — same
pattern as `0009`'s original seed): adds `surya`/`doctr`/
`trocr_handwritten` to the `ocr_providers` catalog with
`is_implemented=True` (real, verified adapters exist) but
`is_enabled=False`/`is_default=False` — an administrator must still
explicitly enable each one once its isolated venv exists on a given
deployment, same "code exists != this deployment has it" convention
`0014` established for the original five providers.

## Related documents

- [storage-guide.md](storage-guide.md) — `StorageService`/MinIO object
  storage layer detail (key scheme, temp vs. permanent, archival).
- [database-standards.md](database-standards.md) — full table list and
  column conventions.
- [assessment-domain-guide.md](assessment-domain-guide.md) — Module 04
  `Exam`/`ExamSession` entities this module's `AnswerScript` references.
- [api-standards.md](api-standards.md) — REST conventions, including the
  multipart-upload pattern this module introduces.
