# Folder Structure

```
/
├── backend/                 FastAPI service (see backend/README.md)
│   ├── app/
│   │   ├── main.py            application factory / entrypoint
│   │   ├── core/                config, logging, security, exceptions, RBAC, constants,
│   │   │                          tenancy.py (Module 03 tenant resolution)
│   │   ├── api/                   routers: health.py (unversioned) + v1/ (versioned:
│   │   │                            IAM endpoints + 20 Academic Domain entity endpoints +
│   │   │                            37 Assessment Domain entity endpoints (Module 04) +
│   │   │                            8 Answer Script OCR Pipeline routers (Module 05) +
│   │   │                            8 Official Exam Content Ingestion & AI Evaluation
│   │   │                            routers (Module 06) + 6 Teacher Review/Result
│   │   │                            Finalization/Analytics routers (Module 07))
│   │   ├── db/                      SQLAlchemy session/base, Redis client, storage.py
│   │   │                              (MinIO client singleton, Module 05)
│   │   ├── middleware/                 request ID, access logs, security headers, rate limit
│   │   ├── models/                       ORM models: user/role/permission/... (Module 02 IAM)
│   │   │                                  plus institution/campus/department/... (Module 03
│   │   │                                  Academic Domain, 21 models incl. user_institution)
│   │   │                                  plus assessment/exam/question/... (Module 04
│   │   │                                  Assessment Domain, 37 models; assessment_base.py
│   │   │                                  holds VersionCounterMixin/ApprovalWorkflowMixin)
│   │   │                                  plus answer_script/ocr_*/processing_history (Module
│   │   │                                  05 OCR Pipeline, 11 models)
│   │   │                                  plus official_exam_document/extracted_*/
│   │   │                                  mark_scheme_range/ai_provider/ai_configuration/
│   │   │                                  answer_evaluation (Module 06, 8 models)
│   │   │                                  plus exam_result/report_job/notification_event
│   │   │                                  (Module 07, 3 models)
│   │   ├── schemas/                        Pydantic v2 request/response contracts, incl.
│   │   │                                    pagination.py (Page[T]/PageParams, Module 03)
│   │   ├── repositories/                     one per model above; tenant_repository.py's
│   │   │                                      TenantScopedRepository is the Module 03 base
│   │   │                                      (reused unmodified by Modules 04/05/06);
│   │   │                                      global_repository.py's GlobalRepository is a
│   │   │                                      Module 05 base for non-tenant-owned entities
│   │   │                                      (OCRProvider, and now AIProvider — Module 06)
│   │   ├── services/                           auth, token, password, user, rbac, session,
│   │   │                                        audit, plus tenant_service.py's
│   │   │                                        TenantScopedService (Module 03 base, reused
│   │   │                                        unmodified by Modules 04/05/06);
│   │   │                                        global_service.py (Module 05, mirrors
│   │   │                                        TenantScopedService minus institution
│   │   │                                        scoping); storage_service.py (MinIO wrapper);
│   │   │                                        ocr/ (provider abstraction + registry + 6
│   │   │                                        adapters, 1 real + 5 stubs);
│   │   │                                        image_processing/ (12-step preprocessing
│   │   │                                        pipeline); text_normalization_service.py;
│   │   │                                        document_structure_service.py;
│   │   │                                        ai/ (Module 06 — AI provider abstraction +
│   │   │                                        registry + 3 adapters, 1 real
│   │   │                                        lexical/statistical + 2 stubs, mirrors ocr/);
│   │   │                                        mark_scheme_service.py,
│   │   │                                        official_document_extraction_service.py,
│   │   │                                        answer_extraction_service.py (Module 06);
│   │   │                                        exam_result_service.py (finalization/locking
│   │   │                                        state machine), analytics_service.py,
│   │   │                                        teacher_review_dashboard_service.py,
│   │   │                                        search_service.py, report_service.py,
│   │   │                                        notification_service.py (Module 07)
│   │   ├── tasks/                                 Celery app + ocr_tasks.py (Module 05 — the
│   │   │                                            first real registered Celery task) +
│   │   │                                            official_document_tasks.py (Module 06 —
│   │   │                                            a new, parallel task reusing Module 05's
│   │   │                                            engine layer exactly, not importing from
│   │   │                                            ocr_tasks.py) + report_tasks.py (Module 07
│   │   │                                            — background PDF/Excel/CSV generation via
│   │   │                                            reportlab/openpyxl/csv)
│   │   └── utils/                                   pure helpers
│   ├── alembic/              migrations: baseline, IAM tables + RBAC seed, Academic Domain
│   │                           tables + permission seed (Module 03), Assessment Domain
│   │                           tables + permission seed (Module 04), OCR Pipeline tables +
│   │                           permission/provider seed (Module 05), Module 06 tables +
│   │                           permission/AI-provider seed (Module 06), Module 07 tables +
│   │                           permission seed (Module 07) — 0001 through 0013
│   ├── tests/                pytest suite
│   ├── pyproject.toml        deps + black/ruff/isort/mypy/pytest config
│   └── Dockerfile            multi-stage: development / production
│
├── frontend/                 React 19 + Vite + TS app (see frontend/README.md)
│   ├── src/
│   │   ├── main.tsx / App.tsx  entrypoint + provider composition
│   │   ├── routes/               React Router route tree
│   │   ├── layouts/                AuthLayout, DashboardLayout
│   │   ├── pages/                    route-level pages; pages/academic/ holds the 11
│   │   │                              Module 03 management screens; pages/assessment/
│   │   │                              holds the 12 Module 04 management screens;
│   │   │                              pages/ocr/ holds the 10 Module 05 screens plus the
│   │   │                              8 Module 06 screens (upload/verification/evaluation)
│   │   │                              plus 6 Module 07 screens (teacher review dashboard,
│   │   │                              result finalization, analytics, reports, search,
│   │   │                              notifications)
│   │   ├── components/                 ui/ (incl. dialog/table/select/textarea, Module 03),
│   │   │                                 layout/ (incl. InstitutionSwitcher, Module 03),
│   │   │                                 common/ (DataTable/FormDialog/... shared shell,
│   │   │                                 reused unchanged by every Module 04/05/06 screen)
│   │   ├── context/                      ThemeProvider, ToastProvider
│   │   ├── store/                          Redux Toolkit (incl. institutionSlice, Module 03)
│   │   ├── api/                              Axios (with auth + tenant-header interceptors)
│   │   │                                       + React Query + one module per backend
│   │   │                                       resource, incl. createCrudApi.ts factory,
│   │   │                                       the 11 Academic Domain (Module 03), 36
│   │   │                                       Assessment Domain (Module 04), 8 OCR
│   │   │                                       Pipeline (Module 05), 8 Official Exam
│   │   │                                       Content/AI Evaluation (Module 06), and 6
│   │   │                                       Teacher Review/Analytics/Reports/Search/
│   │   │                                       Notifications (Module 07) entity modules
│   │   ├── hooks/                              reusable hooks, incl. usePaginatedList/
│   │   │                                        useCrudMutations/useSelectOptions (Module 03,
│   │   │                                        reused unchanged by Modules 04/05/06)
│   │   ├── config/                                env validation (Zod)
│   │   ├── lib/                                     framework-agnostic helpers
│   │   ├── types/                                     shared TS types (incl. academic.ts,
│   │   │                                                assessment.ts, ocr.ts,
│   │   │                                                officialExam.ts, pagination.ts)
│   │   └── tests/                                       unit/ + e2e/
│   ├── package.json
│   └── Dockerfile             multi-stage: development / build / production (nginx)
│
├── shared/                  cross-cutting types/constants consumed by both apps —
│                              constants/roles.ts + constants/permissions.ts (Module 03,
│                              regenerated each module as new PermissionCode values land);
│                              the frontend imports these via a `@shared/*` alias
├── database/                 schema documentation (actual migrations live in backend/alembic)
├── docker/                    infra-only Docker configs (Dockerfiles live with their app)
├── infrastructure/              IaC placeholder (terraform/, k8s/) for cloud deployment
├── monitoring/                    observability config placeholder (prometheus/, grafana/)
├── configs/                         non-secret shared tooling config placeholder
├── storage/                           object storage scratch/docs placeholder (the real
│                                         object storage is MinIO, wired in Module 05 — see
│                                         docs/storage-guide.md; this directory remains docs-only)
│
├── ai/ evaluation/ analytics/ notification/ gateway/
│                             placeholders for future domain modules (see each README.md) —
│                             intentionally empty. `ocr/` was Module 01–04's placeholder for
│                             this domain; Module 05's real OCR code lives under
│                             backend/app/services/ocr/ and backend/app/services/image_processing/
│                             instead (following the established layered-backend convention,
│                             not the top-level-placeholder one) — see docs/ocr-pipeline-guide.md
│
├── docs/                     this documentation set
├── scripts/                  repo-level automation scripts
├── .github/workflows/        CI: lint.yml, test.yml, build.yml, docker.yml
│
├── logs/ uploads/ backups/   gitignored runtime directories (kept via .gitkeep)
│
├── docker-compose.yml        local dev stack: postgres, redis, minio, backend, frontend
├── package.json               npm workspaces root (frontend + shared) + Husky/commitlint
├── .pre-commit-config.yaml     black/isort/ruff + eslint/prettier hooks
├── .editorconfig
└── .env.example                root-level Docker Compose environment template
```

## Where do I put a new domain module?

When Module 02+ adds a real domain (e.g. Authentication, Institutions):

- **Backend**: add `app/models/<domain>.py`, `app/schemas/<domain>.py`,
  `app/repositories/<domain>.py` (subclassing `BaseRepository`),
  `app/services/<domain>.py` (subclassing `BaseService`), and
  `app/api/v1/endpoints/<domain>.py`, then register the router in
  `app/api/v1/router.py`. Import the model module in `alembic/env.py` (or an
  aggregator) so Alembic picks it up for autogeneration.
- **Frontend**: add `src/api/<domain>.ts`, `src/hooks/use<Domain>.ts`,
  `src/pages/<Domain>*.tsx`, and register routes in `src/routes/index.tsx`.

For a tenant-scoped domain (belongs to an `Institution`), subclass
`TenantScopedRepository`/`TenantScopedService`
(`app/repositories/tenant_repository.py`, `app/services/tenant_service.py`)
instead of the bare `BaseRepository`/`BaseService`, and reuse
`createCrudApi`/`usePaginatedList`/`useCrudMutations`/`useSelectOptions` on
the frontend — see [academic-domain-guide.md](academic-domain-guide.md)
for the full pattern established in Module 03.
