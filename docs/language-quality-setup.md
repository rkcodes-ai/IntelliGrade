# Language Quality Intelligence — Setup & Architecture

Step 4.1 milestone: local grammar/spelling/punctuation/capitalization
analysis of student answer text via LanguageTool, running entirely
offline with no paid API and no cloud account.

## Architecture

```
Student Answer Image/PDF
        v
Existing Document Intelligence + Six-Provider OCR Ensemble + Fusion
        v
OCRResult.raw_text (fused, unmodified)
        v
Language Quality Intelligence (app/services/document_intelligence/language_quality.py)
        v
LanguageEvidence  -->  OCRResult.language_quality_metadata (JSON)
        v
AnswerEvidence.language_evidence (additive; existing text-only consumers unaffected)
```

Analysis runs on `OCRResult.raw_text`, not `normalized_text` — this is
deliberate: `raw_text`'s line boundaries (`"\n".join(...)`) match
`OCRResult.disagreement_regions`' `line_index` exactly, which is what
lets a LanguageTool finding be reliably checked against OCR fusion
disagreement/low-confidence evidence. `normalize_text()`'s hyphen-
rejoining and blank-line collapse would otherwise silently shift that
alignment.

## Engine: LanguageTool (local, offline)

- **Version pinned**: 6.6, the last fixed-version "stable" release
  before the upstream project switched to a snapshot-based release
  model (March 2025). Downloaded from
  `https://languagetool.org/download/LanguageTool-stable.zip` and
  extracted into `backend/.languagetool/` (git-ignored — ~390MB,
  never committed; see `.gitignore`).
- **License**: LGPL-2.1-or-later (verified directly against
  `backend/.languagetool/COPYING.txt` in the real downloaded
  distribution — not assumed from memory).
- **Not used**: `language_tool_python` (the PyPI wrapper) — it is
  GPL-3.0-only, a stronger copyleft than LanguageTool's own LGPL-2.1
  core. This project invokes LanguageTool's `languagetool-commandline.jar`
  directly as a subprocess instead, avoiding that license entirely.
- **Not used**: LanguageTool Premium (the paid cloud/API sister
  product) or any remote LanguageTool server — every invocation reads a
  local temp file and runs `java -jar languagetool-commandline.jar
  --json -l <language> <file>` with no network flags.

## Runtime requirement: Java

LanguageTool requires a JVM (Java 17–21). This machine did not have
Java installed prior to this milestone; **Eclipse Temurin 21 JRE** (an
open-source, LGPL/GPL-with-classpath-exception OpenJDK distribution)
was installed via `winget install --id EclipseAdoptium.Temurin.21.JRE`.

If `java` is not yet on `PATH` in a given shell/service (common right
after installation until the shell restarts), set
`LANGUAGETOOL_JAVA_PATH` explicitly, e.g.:

```
LANGUAGETOOL_JAVA_PATH=C:\Program Files\Eclipse Adoptium\jre-21.0.11.10-hotspot\bin\java.exe
```

## Configuration (`app/core/config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `LANGUAGE_QUALITY_ENABLED` | `true` | Master toggle; disabling skips language analysis entirely, OCR/evaluation unaffected. |
| `LANGUAGETOOL_JAVA_PATH` | `None` (auto-resolved) | Explicit `java.exe` path; falls back to the known Temurin install path, then plain `"java"` (PATH). |
| `LANGUAGETOOL_JAR_PATH` | `None` (`backend/.languagetool/languagetool-commandline.jar`) | Explicit jar path override. |
| `LANGUAGETOOL_TIMEOUT_SECONDS` | `30.0` | Bounded subprocess timeout — a hung/slow analysis degrades to `status="FAILED"`, never hangs the Celery worker. |

## Grading policy (non-negotiable)

Language analysis produces **evidence only**. By default it never
affects marks:

- `RubricCriterion.is_language_criterion` (new, additive, nullable-safe
  boolean column, defaults to `false` on every existing row) is the
  **only** way a rubric criterion may consume `LanguageEvidence` for
  scoring.
- `compute_language_criterion_marks()` returns `None` unless
  `is_language_criterion=True` is passed in explicitly, and the
  contribution is always clamped to `[0, max_marks]` for that one
  criterion — it can never affect any other criterion or the overall
  technical score.

## Content protection

- **Technical terms**: a generic seed allowlist (`DEFAULT_TECHNICAL_TERMS`)
  plus an optional per-call `technical_terms` set (from the question/
  model-answer/course metadata) — matched findings are excluded from
  scoring, never deleted from the evidence.
- **Code**: `looks_like_code()` — keyword/symbol-density heuristic (no
  distinct `CODE` region type exists in this project's layout
  vocabulary; Surya's own `Code` label collapses into `OTHER`).
- **Equations**: `looks_like_equation()` — text-level heuristic, plus an
  optional `excluded_char_ranges` parameter for callers with real
  region-level `MathEvidence`/`EQUATION` classification.
- **Short answers / bullet lists**: `is_short_or_fragment_answer()` —
  suppresses only CAPITALIZATION/PUNCTUATION findings (a 2-word answer
  isn't a badly-formed sentence), while SPELLING/GRAMMAR findings on
  short text remain scoring-eligible.
- **OCR uncertainty**: any finding overlapping a low-confidence OCR line
  (< 70.0) or a fusion disagreement region is marked
  `certainty="OCR_UNCERTAIN"` and excluded from scoring — the canonical
  "netw0rk" case (Section 39) is a dedicated, passing test.

## Known, honest limitations (not implemented this milestone)

- **Caching**: no dedicated language-analysis result cache was added.
  Every page's language analysis reruns on each OCR pipeline execution.
  A future milestone could key a cache by
  `hash(raw_text) + language + analyzer_version`, matching the existing
  `extra_metadata`/versioning conventions elsewhere in this codebase.
- **Multilingual/mixed-language span splitting**: `looks_like_code`/
  `looks_like_equation` operate on the whole submitted text, not a
  per-line/per-span content classification; a caller with real
  region-level classification can pass `excluded_char_ranges` for
  finer-grained protection, but the OCR pipeline wiring in
  `ocr_tasks.py` does not yet do this automatically.
- **Teacher-review UI**: no frontend changes were made this milestone
  (Section 60 marks this optional).

## Developer testing

```
cd backend
.venv/Scripts/python.exe -m pytest tests/test_document_intelligence_language_quality.py tests/test_step4_1_security.py -v
```

These tests run real, unmocked LanguageTool subprocess invocations —
Java and `backend/.languagetool/` must be present (see above).
