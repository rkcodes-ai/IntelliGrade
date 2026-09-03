"""Application-wide enums and constants (mirrored in `shared/constants` for the frontend)."""

from enum import StrEnum


class Role(StrEnum):
    """
    Canonical seeded roles. Kept in sync with `shared/constants/roles.ts`.

    This enum exists for seed data and for code that needs to reference one
    of these four roles by name (e.g. "only a super admin may do X"). It is
    NOT the source of truth for authorization — that's the `roles` /
    `permissions` / `role_permissions` DB tables (see
    `app.core.constants.PermissionCode` and `docs/rbac.md`), so new roles
    can be added at runtime without a code change or a new enum member.
    """

    SUPER_ADMIN = "super_admin"
    INSTITUTION_ADMIN = "institution_admin"
    TEACHER = "teacher"
    STUDENT = "student"


class PermissionCode(StrEnum):
    """
    Atomic permission codes, `resource:action`. Seeded into the
    `permissions` table by the `0003_seed_rbac_baseline` migration and
    granted to roles via `role_permissions` — see
    `DEFAULT_ROLE_PERMISSIONS` below and `docs/rbac.md`.
    """

    USERS_CREATE = "users:create"
    USERS_READ = "users:read"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    USERS_LIST = "users:list"
    USERS_ACTIVATE = "users:activate"
    USERS_DEACTIVATE = "users:deactivate"

    ROLES_READ = "roles:read"
    ROLES_LIST = "roles:list"
    ROLES_ASSIGN = "roles:assign"

    PERMISSIONS_READ = "permissions:read"
    PERMISSIONS_LIST = "permissions:list"

    SESSIONS_READ = "sessions:read"
    SESSIONS_REVOKE = "sessions:revoke"

    AUDIT_LOGS_READ = "audit_logs:read"

    # --- Academic Domain (Module 03) ---
    # Purely additive: every code below is new; nothing above this comment
    # was changed. Four codes per entity (CREATE/READ/UPDATE/DELETE) — READ
    # covers both get-by-id and list, DELETE covers both soft-delete and
    # restore. See ADR-014..019 in ARCHITECTURE_DECISIONS.md and
    # docs/academic-domain-guide.md.
    INSTITUTIONS_CREATE = "institutions:create"
    INSTITUTIONS_READ = "institutions:read"
    INSTITUTIONS_UPDATE = "institutions:update"
    INSTITUTIONS_DELETE = "institutions:delete"

    CAMPUSES_CREATE = "campuses:create"
    CAMPUSES_READ = "campuses:read"
    CAMPUSES_UPDATE = "campuses:update"
    CAMPUSES_DELETE = "campuses:delete"

    DEPARTMENTS_CREATE = "departments:create"
    DEPARTMENTS_READ = "departments:read"
    DEPARTMENTS_UPDATE = "departments:update"
    DEPARTMENTS_DELETE = "departments:delete"

    PROGRAMS_CREATE = "programs:create"
    PROGRAMS_READ = "programs:read"
    PROGRAMS_UPDATE = "programs:update"
    PROGRAMS_DELETE = "programs:delete"

    COURSES_CREATE = "courses:create"
    COURSES_READ = "courses:read"
    COURSES_UPDATE = "courses:update"
    COURSES_DELETE = "courses:delete"

    ACADEMIC_YEARS_CREATE = "academic_years:create"
    ACADEMIC_YEARS_READ = "academic_years:read"
    ACADEMIC_YEARS_UPDATE = "academic_years:update"
    ACADEMIC_YEARS_DELETE = "academic_years:delete"

    SEMESTERS_CREATE = "semesters:create"
    SEMESTERS_READ = "semesters:read"
    SEMESTERS_UPDATE = "semesters:update"
    SEMESTERS_DELETE = "semesters:delete"

    ACADEMIC_CALENDAR_CREATE = "academic_calendar:create"
    ACADEMIC_CALENDAR_READ = "academic_calendar:read"
    ACADEMIC_CALENDAR_UPDATE = "academic_calendar:update"
    ACADEMIC_CALENDAR_DELETE = "academic_calendar:delete"

    BATCHES_CREATE = "batches:create"
    BATCHES_READ = "batches:read"
    BATCHES_UPDATE = "batches:update"
    BATCHES_DELETE = "batches:delete"

    SECTIONS_CREATE = "sections:create"
    SECTIONS_READ = "sections:read"
    SECTIONS_UPDATE = "sections:update"
    SECTIONS_DELETE = "sections:delete"

    SUBJECT_CATEGORIES_CREATE = "subject_categories:create"
    SUBJECT_CATEGORIES_READ = "subject_categories:read"
    SUBJECT_CATEGORIES_UPDATE = "subject_categories:update"
    SUBJECT_CATEGORIES_DELETE = "subject_categories:delete"

    SUBJECTS_CREATE = "subjects:create"
    SUBJECTS_READ = "subjects:read"
    SUBJECTS_UPDATE = "subjects:update"
    SUBJECTS_DELETE = "subjects:delete"

    ROOMS_CREATE = "rooms:create"
    ROOMS_READ = "rooms:read"
    ROOMS_UPDATE = "rooms:update"
    ROOMS_DELETE = "rooms:delete"

    SUBJECT_ALLOCATIONS_CREATE = "subject_allocations:create"
    SUBJECT_ALLOCATIONS_READ = "subject_allocations:read"
    SUBJECT_ALLOCATIONS_UPDATE = "subject_allocations:update"
    SUBJECT_ALLOCATIONS_DELETE = "subject_allocations:delete"

    TEACHER_ASSIGNMENTS_CREATE = "teacher_assignments:create"
    TEACHER_ASSIGNMENTS_READ = "teacher_assignments:read"
    TEACHER_ASSIGNMENTS_UPDATE = "teacher_assignments:update"
    TEACHER_ASSIGNMENTS_DELETE = "teacher_assignments:delete"

    STUDENT_ENROLLMENTS_CREATE = "student_enrollments:create"
    STUDENT_ENROLLMENTS_READ = "student_enrollments:read"
    STUDENT_ENROLLMENTS_UPDATE = "student_enrollments:update"
    STUDENT_ENROLLMENTS_DELETE = "student_enrollments:delete"

    ACADEMIC_STATUSES_CREATE = "academic_statuses:create"
    ACADEMIC_STATUSES_READ = "academic_statuses:read"
    ACADEMIC_STATUSES_UPDATE = "academic_statuses:update"
    ACADEMIC_STATUSES_DELETE = "academic_statuses:delete"

    GRADING_POLICIES_CREATE = "grading_policies:create"
    GRADING_POLICIES_READ = "grading_policies:read"
    GRADING_POLICIES_UPDATE = "grading_policies:update"
    GRADING_POLICIES_DELETE = "grading_policies:delete"

    ATTENDANCE_POLICIES_CREATE = "attendance_policies:create"
    ATTENDANCE_POLICIES_READ = "attendance_policies:read"
    ATTENDANCE_POLICIES_UPDATE = "attendance_policies:update"
    ATTENDANCE_POLICIES_DELETE = "attendance_policies:delete"

    CLASS_SCHEDULES_CREATE = "class_schedules:create"
    CLASS_SCHEDULES_READ = "class_schedules:read"
    CLASS_SCHEDULES_UPDATE = "class_schedules:update"
    CLASS_SCHEDULES_DELETE = "class_schedules:delete"

    # --- Assessment Domain (Module 04) ---
    # Purely additive: every code below is new; nothing above this comment
    # was changed. Same CREATE/READ/UPDATE/DELETE-per-entity convention as
    # Module 03, plus a handful of workflow-specific actions (APPROVE/REJECT/
    # ARCHIVE) for the two entities with an editorial approval workflow
    # (Question, QuestionPaper - see ADR-022). See ADR-020..025 in
    # ARCHITECTURE_DECISIONS.md and docs/assessment-domain-guide.md.
    ASSESSMENT_TYPES_CREATE = "assessment_types:create"
    ASSESSMENT_TYPES_READ = "assessment_types:read"
    ASSESSMENT_TYPES_UPDATE = "assessment_types:update"
    ASSESSMENT_TYPES_DELETE = "assessment_types:delete"

    ASSESSMENT_STATUSES_CREATE = "assessment_statuses:create"
    ASSESSMENT_STATUSES_READ = "assessment_statuses:read"
    ASSESSMENT_STATUSES_UPDATE = "assessment_statuses:update"
    ASSESSMENT_STATUSES_DELETE = "assessment_statuses:delete"

    ASSESSMENTS_CREATE = "assessments:create"
    ASSESSMENTS_READ = "assessments:read"
    ASSESSMENTS_UPDATE = "assessments:update"
    ASSESSMENTS_DELETE = "assessments:delete"

    ASSESSMENT_CONFIGURATIONS_CREATE = "assessment_configurations:create"
    ASSESSMENT_CONFIGURATIONS_READ = "assessment_configurations:read"
    ASSESSMENT_CONFIGURATIONS_UPDATE = "assessment_configurations:update"
    ASSESSMENT_CONFIGURATIONS_DELETE = "assessment_configurations:delete"

    EVALUATION_CONFIGURATIONS_CREATE = "evaluation_configurations:create"
    EVALUATION_CONFIGURATIONS_READ = "evaluation_configurations:read"
    EVALUATION_CONFIGURATIONS_UPDATE = "evaluation_configurations:update"
    EVALUATION_CONFIGURATIONS_DELETE = "evaluation_configurations:delete"

    EXAMS_CREATE = "exams:create"
    EXAMS_READ = "exams:read"
    EXAMS_UPDATE = "exams:update"
    EXAMS_DELETE = "exams:delete"

    EXAM_SCHEDULES_CREATE = "exam_schedules:create"
    EXAM_SCHEDULES_READ = "exam_schedules:read"
    EXAM_SCHEDULES_UPDATE = "exam_schedules:update"
    EXAM_SCHEDULES_DELETE = "exam_schedules:delete"

    EXAM_SESSIONS_CREATE = "exam_sessions:create"
    EXAM_SESSIONS_READ = "exam_sessions:read"
    EXAM_SESSIONS_UPDATE = "exam_sessions:update"
    EXAM_SESSIONS_DELETE = "exam_sessions:delete"

    EXAM_INSTRUCTIONS_CREATE = "exam_instructions:create"
    EXAM_INSTRUCTIONS_READ = "exam_instructions:read"
    EXAM_INSTRUCTIONS_UPDATE = "exam_instructions:update"
    EXAM_INSTRUCTIONS_DELETE = "exam_instructions:delete"

    QUESTION_CATEGORIES_CREATE = "question_categories:create"
    QUESTION_CATEGORIES_READ = "question_categories:read"
    QUESTION_CATEGORIES_UPDATE = "question_categories:update"
    QUESTION_CATEGORIES_DELETE = "question_categories:delete"

    QUESTION_TYPES_CREATE = "question_types:create"
    QUESTION_TYPES_READ = "question_types:read"
    QUESTION_TYPES_UPDATE = "question_types:update"
    QUESTION_TYPES_DELETE = "question_types:delete"

    DIFFICULTY_LEVELS_CREATE = "difficulty_levels:create"
    DIFFICULTY_LEVELS_READ = "difficulty_levels:read"
    DIFFICULTY_LEVELS_UPDATE = "difficulty_levels:update"
    DIFFICULTY_LEVELS_DELETE = "difficulty_levels:delete"

    BLOOM_TAXONOMY_LEVELS_CREATE = "bloom_taxonomy_levels:create"
    BLOOM_TAXONOMY_LEVELS_READ = "bloom_taxonomy_levels:read"
    BLOOM_TAXONOMY_LEVELS_UPDATE = "bloom_taxonomy_levels:update"
    BLOOM_TAXONOMY_LEVELS_DELETE = "bloom_taxonomy_levels:delete"

    QUESTIONS_CREATE = "questions:create"
    QUESTIONS_READ = "questions:read"
    QUESTIONS_UPDATE = "questions:update"
    QUESTIONS_DELETE = "questions:delete"

    QUESTION_VERSIONS_CREATE = "question_versions:create"
    QUESTION_VERSIONS_READ = "question_versions:read"
    QUESTION_VERSIONS_UPDATE = "question_versions:update"
    QUESTION_VERSIONS_DELETE = "question_versions:delete"

    QUESTION_APPROVALS_CREATE = "question_approvals:create"
    QUESTION_APPROVALS_READ = "question_approvals:read"
    QUESTION_APPROVALS_UPDATE = "question_approvals:update"
    QUESTION_APPROVALS_DELETE = "question_approvals:delete"

    QUESTION_REVIEWS_CREATE = "question_reviews:create"
    QUESTION_REVIEWS_READ = "question_reviews:read"
    QUESTION_REVIEWS_UPDATE = "question_reviews:update"
    QUESTION_REVIEWS_DELETE = "question_reviews:delete"

    QUESTION_TAGS_CREATE = "question_tags:create"
    QUESTION_TAGS_READ = "question_tags:read"
    QUESTION_TAGS_UPDATE = "question_tags:update"
    QUESTION_TAGS_DELETE = "question_tags:delete"

    QUESTION_BLUEPRINTS_CREATE = "question_blueprints:create"
    QUESTION_BLUEPRINTS_READ = "question_blueprints:read"
    QUESTION_BLUEPRINTS_UPDATE = "question_blueprints:update"
    QUESTION_BLUEPRINTS_DELETE = "question_blueprints:delete"

    QUESTION_BLUEPRINT_SECTIONS_CREATE = "question_blueprint_sections:create"
    QUESTION_BLUEPRINT_SECTIONS_READ = "question_blueprint_sections:read"
    QUESTION_BLUEPRINT_SECTIONS_UPDATE = "question_blueprint_sections:update"
    QUESTION_BLUEPRINT_SECTIONS_DELETE = "question_blueprint_sections:delete"

    QUESTION_PAPER_TEMPLATES_CREATE = "question_paper_templates:create"
    QUESTION_PAPER_TEMPLATES_READ = "question_paper_templates:read"
    QUESTION_PAPER_TEMPLATES_UPDATE = "question_paper_templates:update"
    QUESTION_PAPER_TEMPLATES_DELETE = "question_paper_templates:delete"

    QUESTION_PAPERS_CREATE = "question_papers:create"
    QUESTION_PAPERS_READ = "question_papers:read"
    QUESTION_PAPERS_UPDATE = "question_papers:update"
    QUESTION_PAPERS_DELETE = "question_papers:delete"

    QUESTION_PAPER_VERSIONS_CREATE = "question_paper_versions:create"
    QUESTION_PAPER_VERSIONS_READ = "question_paper_versions:read"
    QUESTION_PAPER_VERSIONS_UPDATE = "question_paper_versions:update"
    QUESTION_PAPER_VERSIONS_DELETE = "question_paper_versions:delete"

    QUESTION_PAPER_SECTIONS_CREATE = "question_paper_sections:create"
    QUESTION_PAPER_SECTIONS_READ = "question_paper_sections:read"
    QUESTION_PAPER_SECTIONS_UPDATE = "question_paper_sections:update"
    QUESTION_PAPER_SECTIONS_DELETE = "question_paper_sections:delete"

    QUESTION_PAPER_QUESTION_MAPPINGS_CREATE = "question_paper_question_mappings:create"
    QUESTION_PAPER_QUESTION_MAPPINGS_READ = "question_paper_question_mappings:read"
    QUESTION_PAPER_QUESTION_MAPPINGS_UPDATE = "question_paper_question_mappings:update"
    QUESTION_PAPER_QUESTION_MAPPINGS_DELETE = "question_paper_question_mappings:delete"

    RANDOMIZATION_STRATEGIES_CREATE = "randomization_strategies:create"
    RANDOMIZATION_STRATEGIES_READ = "randomization_strategies:read"
    RANDOMIZATION_STRATEGIES_UPDATE = "randomization_strategies:update"
    RANDOMIZATION_STRATEGIES_DELETE = "randomization_strategies:delete"

    ANSWER_KEYS_CREATE = "answer_keys:create"
    ANSWER_KEYS_READ = "answer_keys:read"
    ANSWER_KEYS_UPDATE = "answer_keys:update"
    ANSWER_KEYS_DELETE = "answer_keys:delete"

    MODEL_ANSWERS_CREATE = "model_answers:create"
    MODEL_ANSWERS_READ = "model_answers:read"
    MODEL_ANSWERS_UPDATE = "model_answers:update"
    MODEL_ANSWERS_DELETE = "model_answers:delete"

    ALTERNATIVE_ANSWERS_CREATE = "alternative_answers:create"
    ALTERNATIVE_ANSWERS_READ = "alternative_answers:read"
    ALTERNATIVE_ANSWERS_UPDATE = "alternative_answers:update"
    ALTERNATIVE_ANSWERS_DELETE = "alternative_answers:delete"

    RUBRICS_CREATE = "rubrics:create"
    RUBRICS_READ = "rubrics:read"
    RUBRICS_UPDATE = "rubrics:update"
    RUBRICS_DELETE = "rubrics:delete"

    RUBRIC_CRITERIA_CREATE = "rubric_criteria:create"
    RUBRIC_CRITERIA_READ = "rubric_criteria:read"
    RUBRIC_CRITERIA_UPDATE = "rubric_criteria:update"
    RUBRIC_CRITERIA_DELETE = "rubric_criteria:delete"

    MARK_DISTRIBUTIONS_CREATE = "mark_distributions:create"
    MARK_DISTRIBUTIONS_READ = "mark_distributions:read"
    MARK_DISTRIBUTIONS_UPDATE = "mark_distributions:update"
    MARK_DISTRIBUTIONS_DELETE = "mark_distributions:delete"

    EXPECTED_KEYWORDS_CREATE = "expected_keywords:create"
    EXPECTED_KEYWORDS_READ = "expected_keywords:read"
    EXPECTED_KEYWORDS_UPDATE = "expected_keywords:update"
    EXPECTED_KEYWORDS_DELETE = "expected_keywords:delete"

    EXPECTED_CONCEPTS_CREATE = "expected_concepts:create"
    EXPECTED_CONCEPTS_READ = "expected_concepts:read"
    EXPECTED_CONCEPTS_UPDATE = "expected_concepts:update"
    EXPECTED_CONCEPTS_DELETE = "expected_concepts:delete"

    REFERENCE_NOTES_CREATE = "reference_notes:create"
    REFERENCE_NOTES_READ = "reference_notes:read"
    REFERENCE_NOTES_UPDATE = "reference_notes:update"
    REFERENCE_NOTES_DELETE = "reference_notes:delete"

    EVALUATION_HISTORY_CREATE = "evaluation_history:create"
    EVALUATION_HISTORY_READ = "evaluation_history:read"

    QUESTIONS_APPROVE = "questions:approve"
    QUESTIONS_REJECT = "questions:reject"
    QUESTIONS_ARCHIVE = "questions:archive"
    QUESTION_PAPERS_APPROVE = "question_papers:approve"
    QUESTION_PAPERS_REJECT = "question_papers:reject"
    QUESTION_PAPERS_ARCHIVE = "question_papers:archive"

    # --- Answer Script OCR Pipeline (Module 05) ---
    ANSWER_SCRIPTS_CREATE = "answer_scripts:create"
    ANSWER_SCRIPTS_READ = "answer_scripts:read"
    ANSWER_SCRIPTS_UPDATE = "answer_scripts:update"
    ANSWER_SCRIPTS_DELETE = "answer_scripts:delete"
    ANSWER_SCRIPTS_RETRY = "answer_scripts:retry"
    ANSWER_SCRIPTS_CANCEL = "answer_scripts:cancel"

    ANSWER_SCRIPT_PAGES_READ = "answer_script_pages:read"

    UPLOAD_JOBS_CREATE = "upload_jobs:create"
    UPLOAD_JOBS_READ = "upload_jobs:read"

    # Global system catalog (see ADR-028) — :update is super_admin-only
    # (enable/disable an engine is a platform toggle, not tenant content).
    OCR_PROVIDERS_READ = "ocr_providers:read"
    OCR_PROVIDERS_UPDATE = "ocr_providers:update"

    OCR_CONFIGURATIONS_CREATE = "ocr_configurations:create"
    OCR_CONFIGURATIONS_READ = "ocr_configurations:read"
    OCR_CONFIGURATIONS_UPDATE = "ocr_configurations:update"
    OCR_CONFIGURATIONS_DELETE = "ocr_configurations:delete"

    OCR_JOBS_READ = "ocr_jobs:read"
    OCR_JOBS_CREATE = "ocr_jobs:create"
    OCR_JOBS_CANCEL = "ocr_jobs:cancel"

    # Read-only: OCRBlock/OCRLine/OCRWord are nested under one OCRResult
    # and share this same permission code (see docs/ocr-pipeline-guide.md).
    OCR_RESULTS_READ = "ocr_results:read"

    # Append-only pipeline-stage log (see ADR-030) — read-only.
    PROCESSING_HISTORY_READ = "processing_history:read"

    # --- Official Exam Content Ingestion & AI Evaluation (Module 06) ---
    OFFICIAL_EXAM_DOCUMENTS_CREATE = "official_exam_documents:create"
    OFFICIAL_EXAM_DOCUMENTS_READ = "official_exam_documents:read"
    OFFICIAL_EXAM_DOCUMENTS_UPDATE = "official_exam_documents:update"
    OFFICIAL_EXAM_DOCUMENTS_DELETE = "official_exam_documents:delete"
    OFFICIAL_EXAM_DOCUMENTS_RETRY = "official_exam_documents:retry"
    OFFICIAL_EXAM_DOCUMENTS_CANCEL = "official_exam_documents:cancel"

    OFFICIAL_EXAM_DOCUMENT_PAGES_READ = "official_exam_document_pages:read"

    # Verification workflow (Stage: Teacher Verification) — :update edits
    # the extracted text/marks, :verify marks a row as teacher-confirmed
    # (see ADR-035/ADR-037). Never requires Question Bank promotion.
    EXTRACTED_QUESTIONS_READ = "extracted_questions:read"
    EXTRACTED_QUESTIONS_UPDATE = "extracted_questions:update"
    EXTRACTED_QUESTIONS_VERIFY = "extracted_questions:verify"

    EXTRACTED_MODEL_ANSWERS_READ = "extracted_model_answers:read"
    EXTRACTED_MODEL_ANSWERS_UPDATE = "extracted_model_answers:update"
    EXTRACTED_MODEL_ANSWERS_VERIFY = "extracted_model_answers:verify"

    MARK_SCHEME_RANGES_READ = "mark_scheme_ranges:read"
    MARK_SCHEME_RANGES_UPDATE = "mark_scheme_ranges:update"
    MARK_SCHEME_RANGES_VERIFY = "mark_scheme_ranges:verify"

    # Global system catalog (see ADR-041, mirrors OCR_PROVIDERS_*) —
    # :update is super_admin-only, same platform-toggle reasoning.
    AI_PROVIDERS_READ = "ai_providers:read"
    AI_PROVIDERS_UPDATE = "ai_providers:update"

    AI_CONFIGURATIONS_CREATE = "ai_configurations:create"
    AI_CONFIGURATIONS_READ = "ai_configurations:read"
    AI_CONFIGURATIONS_UPDATE = "ai_configurations:update"
    AI_CONFIGURATIONS_DELETE = "ai_configurations:delete"

    # AI Reference Answer Builder milestone. :create triggers
    # `ReferenceAnswerService.generate()`; :approve/:reject are the
    # teacher-verification actions; :regenerate creates a new version.
    AI_REFERENCE_ANSWERS_READ = "ai_reference_answers:read"
    AI_REFERENCE_ANSWERS_CREATE = "ai_reference_answers:create"
    AI_REFERENCE_ANSWERS_APPROVE = "ai_reference_answers:approve"
    AI_REFERENCE_ANSWERS_REJECT = "ai_reference_answers:reject"
    AI_REFERENCE_ANSWERS_REGENERATE = "ai_reference_answers:regenerate"

    # :create triggers `AnswerEvaluationService.evaluate_question()`;
    # :confirm/:override are the two Teacher Review actions (ADR-040).
    # :reject/:rerun are Module 07's additions (ADR-043).
    ANSWER_EVALUATIONS_READ = "answer_evaluations:read"
    ANSWER_EVALUATIONS_CREATE = "answer_evaluations:create"
    ANSWER_EVALUATIONS_CONFIRM = "answer_evaluations:confirm"
    ANSWER_EVALUATIONS_OVERRIDE = "answer_evaluations:override"
    ANSWER_EVALUATIONS_REJECT = "answer_evaluations:reject"
    ANSWER_EVALUATIONS_RERUN = "answer_evaluations:rerun"

    # --- Teacher Review, Result Finalization & Analytics (Module 07) ---
    # See ADR-042..048. `exam_results:*` is the Result Finalization/Locking
    # state machine (:finalize covers per-student/per-exam/per-batch bulk
    # finalization — the granularity is a request-body field, not a
    # separate permission — :approve/:lock/:publish are the remaining
    # forward transitions, :unlock is the one backward transition and is
    # deliberately its own, more tightly-granted permission — see ADR-042).
    TEACHER_REVIEW_DASHBOARD_READ = "teacher_review_dashboard:read"

    EXAM_RESULTS_READ = "exam_results:read"
    EXAM_RESULTS_FINALIZE = "exam_results:finalize"
    EXAM_RESULTS_APPROVE = "exam_results:approve"
    EXAM_RESULTS_LOCK = "exam_results:lock"
    EXAM_RESULTS_UNLOCK = "exam_results:unlock"
    EXAM_RESULTS_PUBLISH = "exam_results:publish"

    ANALYTICS_READ = "analytics:read"

    REPORTS_READ = "reports:read"
    REPORTS_GENERATE = "reports:generate"

    SEARCH_READ = "search:read"

    NOTIFICATIONS_READ = "notifications:read"
    NOTIFICATIONS_UPDATE = "notifications:update"


# Academic Domain (Module 03) entity prefixes — matches each PermissionCode
# resource segment exactly (e.g. "campuses" -> CAMPUSES_CREATE/READ/UPDATE/
# DELETE), used below to build role grants without repeating 80 enum names
# by hand. Institution itself is listed separately since institution_admin
# gets a narrower grant on it (read-only — creating/deleting an institution
# is a platform-level, super-admin-only action).
_ACADEMIC_ENTITY_PREFIXES: tuple[str, ...] = (
    "campuses",
    "departments",
    "programs",
    "courses",
    "academic_years",
    "semesters",
    "academic_calendar",
    "batches",
    "sections",
    "subject_categories",
    "subjects",
    "rooms",
    "subject_allocations",
    "teacher_assignments",
    "student_enrollments",
    "academic_statuses",
    "grading_policies",
    "attendance_policies",
    "class_schedules",
)

_ACADEMIC_FULL_CRUD: tuple[PermissionCode, ...] = tuple(
    PermissionCode(f"{prefix}:{action}")
    for prefix in _ACADEMIC_ENTITY_PREFIXES
    for action in ("create", "read", "update", "delete")
)

_ACADEMIC_READ_ONLY: tuple[PermissionCode, ...] = tuple(
    PermissionCode(f"{prefix}:read") for prefix in ("institutions", *_ACADEMIC_ENTITY_PREFIXES)
)

# Assessment Domain (Module 04) entity prefixes, split into three groups
# reflecting real editorial responsibility (see ADR-025) rather than a
# single blanket grant per role:
#   - lookups: simple reference tables (types/levels/tags/categories).
#   - content: entities a teacher actually authors (questions, papers,
#     rubrics, answer keys, ...) — teacher gets full CRUD here.
#   - admin_only: exam scheduling/configuration and the approval-decision
#     record itself — teacher gets read-only, institution_admin gets CRUD.
_ASSESSMENT_LOOKUP_PREFIXES: tuple[str, ...] = (
    "assessment_types",
    "assessment_statuses",
    "question_categories",
    "question_types",
    "difficulty_levels",
    "bloom_taxonomy_levels",
    "question_tags",
)

_ASSESSMENT_CONTENT_PREFIXES: tuple[str, ...] = (
    "questions",
    "question_versions",
    "question_reviews",
    "question_blueprints",
    "question_blueprint_sections",
    "question_paper_templates",
    "question_papers",
    "question_paper_versions",
    "question_paper_sections",
    "question_paper_question_mappings",
    "randomization_strategies",
    "answer_keys",
    "model_answers",
    "alternative_answers",
    "rubrics",
    "rubric_criteria",
    "mark_distributions",
    "expected_keywords",
    "expected_concepts",
    "reference_notes",
)

_ASSESSMENT_ADMIN_ONLY_PREFIXES: tuple[str, ...] = (
    "assessments",
    "assessment_configurations",
    "evaluation_configurations",
    "exams",
    "exam_schedules",
    "exam_sessions",
    "exam_instructions",
    "question_approvals",
)

# Entities a student may read by default — deliberately narrow (see
# ADR-025): what's being examined and when, never the question bank,
# answer keys, rubrics, or papers themselves.
_ASSESSMENT_STUDENT_READABLE_PREFIXES: tuple[str, ...] = (
    "assessments",
    "exams",
    "exam_schedules",
    "exam_instructions",
)

_ASSESSMENT_FULL_CRUD: tuple[PermissionCode, ...] = tuple(
    PermissionCode(f"{prefix}:{action}")
    for prefix in (
        *_ASSESSMENT_LOOKUP_PREFIXES,
        *_ASSESSMENT_CONTENT_PREFIXES,
        *_ASSESSMENT_ADMIN_ONLY_PREFIXES,
    )
    for action in ("create", "read", "update", "delete")
) + (
    PermissionCode.EVALUATION_HISTORY_CREATE,
    PermissionCode.EVALUATION_HISTORY_READ,
    PermissionCode.QUESTIONS_APPROVE,
    PermissionCode.QUESTIONS_REJECT,
    PermissionCode.QUESTIONS_ARCHIVE,
    PermissionCode.QUESTION_PAPERS_APPROVE,
    PermissionCode.QUESTION_PAPERS_REJECT,
    PermissionCode.QUESTION_PAPERS_ARCHIVE,
)

_ASSESSMENT_TEACHER_GRANTS: tuple[PermissionCode, ...] = (
    tuple(
        PermissionCode(f"{prefix}:{action}")
        for prefix in (*_ASSESSMENT_LOOKUP_PREFIXES, *_ASSESSMENT_CONTENT_PREFIXES)
        for action in ("create", "read", "update", "delete")
    )
    + tuple(PermissionCode(f"{prefix}:read") for prefix in _ASSESSMENT_ADMIN_ONLY_PREFIXES)
    + (PermissionCode.EVALUATION_HISTORY_READ,)
)

_ASSESSMENT_STUDENT_GRANTS: tuple[PermissionCode, ...] = tuple(
    PermissionCode(f"{prefix}:read") for prefix in _ASSESSMENT_STUDENT_READABLE_PREFIXES
)

# Answer Script OCR Pipeline (Module 05). Students get zero default access
# (see ADR-034 — uploaded scripts are ungraded student work, the same
# sensitivity class as Module 04's answer keys). teacher gets create/read/
# retry on the content they upload plus read on every derived/system
# artifact; institution_admin additionally gets delete/cancel and full
# OCRConfiguration management; OCR_PROVIDERS_UPDATE (enabling/disabling an
# engine) is reserved for super_admin only — a platform-level toggle, not
# granted to institution_admin at all.
_OCR_READ_ONLY_GRANTS: tuple[PermissionCode, ...] = (
    PermissionCode.ANSWER_SCRIPT_PAGES_READ,
    PermissionCode.UPLOAD_JOBS_READ,
    PermissionCode.OCR_PROVIDERS_READ,
    PermissionCode.OCR_CONFIGURATIONS_READ,
    PermissionCode.OCR_JOBS_READ,
    PermissionCode.OCR_RESULTS_READ,
    PermissionCode.PROCESSING_HISTORY_READ,
)

_OCR_ADMIN_FULL_CRUD: tuple[PermissionCode, ...] = (
    PermissionCode.ANSWER_SCRIPTS_CREATE,
    PermissionCode.ANSWER_SCRIPTS_READ,
    PermissionCode.ANSWER_SCRIPTS_UPDATE,
    PermissionCode.ANSWER_SCRIPTS_DELETE,
    PermissionCode.ANSWER_SCRIPTS_RETRY,
    PermissionCode.ANSWER_SCRIPTS_CANCEL,
    PermissionCode.UPLOAD_JOBS_CREATE,
    PermissionCode.OCR_CONFIGURATIONS_CREATE,
    PermissionCode.OCR_CONFIGURATIONS_UPDATE,
    PermissionCode.OCR_CONFIGURATIONS_DELETE,
    PermissionCode.OCR_JOBS_CREATE,
    PermissionCode.OCR_JOBS_CANCEL,
    *_OCR_READ_ONLY_GRANTS,
)

_OCR_TEACHER_GRANTS: tuple[PermissionCode, ...] = (
    PermissionCode.ANSWER_SCRIPTS_CREATE,
    PermissionCode.ANSWER_SCRIPTS_READ,
    PermissionCode.ANSWER_SCRIPTS_RETRY,
    PermissionCode.UPLOAD_JOBS_CREATE,
    PermissionCode.OCR_JOBS_CREATE,
    *_OCR_READ_ONLY_GRANTS,
)

# Official Exam Content Ingestion & AI Evaluation (Module 06). Students
# get zero default access — official model answers and mark schemes are
# more sensitive than Module 05's ungraded scripts (leaking either before/
# during an exam window is a serious integrity issue, not just a privacy
# one). teacher does the upload + Teacher Verification + Teacher Review
# work (create documents, update/verify extracted content, trigger
# evaluation, confirm/override results); institution_admin additionally
# gets delete/retry/cancel and full AIConfiguration management;
# AI_PROVIDERS_UPDATE is super_admin-only, same platform-toggle reasoning
# as OCR_PROVIDERS_UPDATE.
_AI_READ_ONLY_GRANTS: tuple[PermissionCode, ...] = (
    PermissionCode.OFFICIAL_EXAM_DOCUMENTS_READ,
    PermissionCode.OFFICIAL_EXAM_DOCUMENT_PAGES_READ,
    PermissionCode.EXTRACTED_QUESTIONS_READ,
    PermissionCode.EXTRACTED_MODEL_ANSWERS_READ,
    PermissionCode.MARK_SCHEME_RANGES_READ,
    PermissionCode.AI_PROVIDERS_READ,
    PermissionCode.AI_CONFIGURATIONS_READ,
    PermissionCode.AI_REFERENCE_ANSWERS_READ,
    PermissionCode.ANSWER_EVALUATIONS_READ,
)

_AI_VERIFICATION_AND_REVIEW_GRANTS: tuple[PermissionCode, ...] = (
    PermissionCode.OFFICIAL_EXAM_DOCUMENTS_CREATE,
    PermissionCode.EXTRACTED_QUESTIONS_UPDATE,
    PermissionCode.EXTRACTED_QUESTIONS_VERIFY,
    PermissionCode.EXTRACTED_MODEL_ANSWERS_UPDATE,
    PermissionCode.EXTRACTED_MODEL_ANSWERS_VERIFY,
    PermissionCode.MARK_SCHEME_RANGES_UPDATE,
    PermissionCode.MARK_SCHEME_RANGES_VERIFY,
    PermissionCode.AI_REFERENCE_ANSWERS_CREATE,
    PermissionCode.AI_REFERENCE_ANSWERS_APPROVE,
    PermissionCode.AI_REFERENCE_ANSWERS_REJECT,
    PermissionCode.AI_REFERENCE_ANSWERS_REGENERATE,
    PermissionCode.ANSWER_EVALUATIONS_CREATE,
    PermissionCode.ANSWER_EVALUATIONS_CONFIRM,
    PermissionCode.ANSWER_EVALUATIONS_OVERRIDE,
)

_AI_ADMIN_FULL_CRUD: tuple[PermissionCode, ...] = (
    PermissionCode.OFFICIAL_EXAM_DOCUMENTS_UPDATE,
    PermissionCode.OFFICIAL_EXAM_DOCUMENTS_DELETE,
    PermissionCode.OFFICIAL_EXAM_DOCUMENTS_RETRY,
    PermissionCode.OFFICIAL_EXAM_DOCUMENTS_CANCEL,
    PermissionCode.AI_CONFIGURATIONS_CREATE,
    PermissionCode.AI_CONFIGURATIONS_UPDATE,
    PermissionCode.AI_CONFIGURATIONS_DELETE,
    *_AI_VERIFICATION_AND_REVIEW_GRANTS,
    *_AI_READ_ONLY_GRANTS,
)

_AI_TEACHER_GRANTS: tuple[PermissionCode, ...] = (
    *_AI_VERIFICATION_AND_REVIEW_GRANTS,
    *_AI_READ_ONLY_GRANTS,
)

# Teacher Review, Result Finalization & Analytics (Module 07). Students get
# zero default access (ADR-048 — no model answers, marks, confidence, or
# comments). teacher does the day-to-day review/finalization/analytics/
# reports/search/notifications work; institution_admin additionally gets
# the one backward transition (:unlock) — reopening a locked/published
# result is an administrative override action, not a routine teacher
# action, so it is deliberately withheld from the teacher's default grant
# (a teacher can request an unlock; only an institution_admin/super_admin
# grants it, mirroring the least-privilege reasoning already used for
# `OCR_PROVIDERS_UPDATE`/`AI_PROVIDERS_UPDATE`).
_REVIEW_TEACHER_GRANTS: tuple[PermissionCode, ...] = (
    PermissionCode.ANSWER_EVALUATIONS_REJECT,
    PermissionCode.ANSWER_EVALUATIONS_RERUN,
    PermissionCode.TEACHER_REVIEW_DASHBOARD_READ,
    PermissionCode.EXAM_RESULTS_READ,
    PermissionCode.EXAM_RESULTS_FINALIZE,
    PermissionCode.EXAM_RESULTS_APPROVE,
    PermissionCode.EXAM_RESULTS_LOCK,
    PermissionCode.EXAM_RESULTS_PUBLISH,
    PermissionCode.ANALYTICS_READ,
    PermissionCode.REPORTS_READ,
    PermissionCode.REPORTS_GENERATE,
    PermissionCode.SEARCH_READ,
    PermissionCode.NOTIFICATIONS_READ,
    PermissionCode.NOTIFICATIONS_UPDATE,
)

_REVIEW_ADMIN_GRANTS: tuple[PermissionCode, ...] = (
    PermissionCode.EXAM_RESULTS_UNLOCK,
    *_REVIEW_TEACHER_GRANTS,
)

# Default grants applied by the seed migration. Purely a starting point —
# operators can regrant permissions per-role afterward via the (future)
# admin RBAC UI without touching code, which is the whole point of keeping
# permissions independent of roles.
DEFAULT_ROLE_PERMISSIONS: dict[Role, tuple[PermissionCode, ...]] = {
    Role.SUPER_ADMIN: tuple(PermissionCode),  # every permission
    Role.INSTITUTION_ADMIN: (
        PermissionCode.USERS_CREATE,
        PermissionCode.USERS_READ,
        PermissionCode.USERS_UPDATE,
        PermissionCode.USERS_LIST,
        PermissionCode.USERS_ACTIVATE,
        PermissionCode.USERS_DEACTIVATE,
        PermissionCode.ROLES_READ,
        PermissionCode.ROLES_LIST,
        PermissionCode.ROLES_ASSIGN,
        PermissionCode.PERMISSIONS_READ,
        PermissionCode.PERMISSIONS_LIST,
        PermissionCode.SESSIONS_READ,
        PermissionCode.SESSIONS_REVOKE,
        PermissionCode.AUDIT_LOGS_READ,
        PermissionCode.INSTITUTIONS_READ,
        *_ACADEMIC_FULL_CRUD,
        *_ASSESSMENT_FULL_CRUD,
        *_OCR_ADMIN_FULL_CRUD,
        *_AI_ADMIN_FULL_CRUD,
        *_REVIEW_ADMIN_GRANTS,
    ),
    Role.TEACHER: (
        PermissionCode.USERS_READ,
        PermissionCode.SESSIONS_READ,
        PermissionCode.SESSIONS_REVOKE,
        *_ACADEMIC_READ_ONLY,
        *_ASSESSMENT_TEACHER_GRANTS,
        *_OCR_TEACHER_GRANTS,
        *_AI_TEACHER_GRANTS,
        *_REVIEW_TEACHER_GRANTS,
    ),
    Role.STUDENT: (
        PermissionCode.SESSIONS_READ,
        PermissionCode.SESSIONS_REVOKE,
        *_ACADEMIC_READ_ONLY,
        *_ASSESSMENT_STUDENT_GRANTS,
        # Zero Module 05/06 grants — see ADR-034 (Module 05) and Module
        # 06's design decisions (official model answers/mark schemes are
        # more sensitive than ungraded scripts). Module 07 (ADR-048) is
        # the same "no model answers, marks, confidence scores, or
        # teacher comments" default, with one deliberate, narrow
        # exception: NotificationEvent read/mark-read. Every notification
        # endpoint is self-scoped to `current_user.id` as recipient (see
        # `app/api/v1/endpoints/notifications.py`) — a student can only
        # ever see their own "your result was published"-style events,
        # never another student's, and never any evaluation content
        # (confidence/marks/comments), so this doesn't reopen the
        # restriction those other grants protect.
        PermissionCode.NOTIFICATIONS_READ,
        PermissionCode.NOTIFICATIONS_UPDATE,
    ),
}


class AuditAction(StrEnum):
    """Event names written to `audit_logs` — see `app.services.audit_service`."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REUSE_DETECTED = "token_reuse_detected"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_COMPLETE = "password_reset_complete"
    PROFILE_UPDATE = "profile_update"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_DELETED = "user_deleted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    SESSION_REVOKED = "session_revoked"
    ACCOUNT_LOCKED = "account_locked"

    # --- Academic Domain (Module 03) ---
    # Generic, resource-agnostic action names — the concrete entity is
    # already captured by AuditLog.resource_type (e.g. "campus", "subject"),
    # so this stays 7 entries instead of ~100 (one CREATED/UPDATED/etc. per
    # entity). Purely additive: nothing above this comment changed.
    ACADEMIC_ENTITY_CREATED = "academic_entity_created"
    ACADEMIC_ENTITY_UPDATED = "academic_entity_updated"
    ACADEMIC_ENTITY_DELETED = "academic_entity_deleted"
    ACADEMIC_ENTITY_RESTORED = "academic_entity_restored"
    ACADEMIC_ASSIGNMENT_CREATED = "academic_assignment_created"
    ACADEMIC_ENROLLMENT_CREATED = "academic_enrollment_created"
    ACADEMIC_STATUS_CHANGED = "academic_status_changed"

    # --- Assessment Domain (Module 04) ---
    # Question creation/update reuse ACADEMIC_ENTITY_CREATED/UPDATED above
    # (already resource-agnostic); these six are the genuinely new action
    # *types* named in the prompt's Audit Logging section (approval/
    # rejection/paper-generation/answer-key/rubric/exam-schedule are not
    # generic create/update — they're distinct workflow events).
    QUESTION_APPROVED = "question_approved"
    QUESTION_REJECTED = "question_rejected"
    QUESTION_PAPER_GENERATED = "question_paper_generated"
    ANSWER_KEY_UPDATED = "answer_key_updated"
    RUBRIC_UPDATED = "rubric_updated"
    EXAM_SCHEDULE_UPDATED = "exam_schedule_updated"

    # --- Answer Script OCR Pipeline (Module 05) ---
    # Human-initiated actions only — see ADR-030 for why the pipeline's own
    # automatic stage transitions go to ProcessingHistory instead, not here.
    ANSWER_SCRIPT_UPLOADED = "answer_script_uploaded"
    ANSWER_SCRIPT_DELETED = "answer_script_deleted"
    ANSWER_SCRIPT_RETRY_REQUESTED = "answer_script_retry_requested"
    OCR_EXECUTION_STARTED = "ocr_execution_started"
    OCR_PROCESSING_COMPLETED = "ocr_processing_completed"
    OCR_PROCESSING_FAILED = "ocr_processing_failed"
    OCR_JOB_CANCELLED = "ocr_job_cancelled"

    # --- Official Exam Content Ingestion & AI Evaluation (Module 06) ---
    OFFICIAL_EXAM_DOCUMENT_UPLOADED = "official_exam_document_uploaded"
    OFFICIAL_EXAM_DOCUMENT_DELETED = "official_exam_document_deleted"
    OFFICIAL_EXAM_DOCUMENT_RETRY_REQUESTED = "official_exam_document_retry_requested"
    OFFICIAL_EXAM_DOCUMENT_CANCELLED = "official_exam_document_cancelled"
    EXTRACTED_QUESTION_VERIFIED = "extracted_question_verified"
    EXTRACTED_MODEL_ANSWER_VERIFIED = "extracted_model_answer_verified"
    MARK_SCHEME_RANGE_VERIFIED = "mark_scheme_range_verified"
    # AI Reference Answer Builder milestone.
    AI_REFERENCE_ANSWER_GENERATION_REQUESTED = "ai_reference_answer_generation_requested"
    AI_REFERENCE_ANSWER_GENERATED = "ai_reference_answer_generated"
    AI_REFERENCE_ANSWER_GENERATION_FAILED = "ai_reference_answer_generation_failed"
    AI_REFERENCE_ANSWER_APPROVED = "ai_reference_answer_approved"
    AI_REFERENCE_ANSWER_REJECTED = "ai_reference_answer_rejected"
    AI_REFERENCE_ANSWER_REGENERATION_REQUESTED = "ai_reference_answer_regeneration_requested"
    ANSWER_EVALUATION_GENERATED = "answer_evaluation_generated"
    ANSWER_EVALUATION_CONFIRMED = "answer_evaluation_confirmed"
    ANSWER_EVALUATION_OVERRIDDEN = "answer_evaluation_overridden"

    # --- Teacher Review, Result Finalization & Analytics (Module 07) ---
    # See ADR-047. Confirm/override reuse the two actions above unchanged.
    ANSWER_EVALUATION_REJECTED = "answer_evaluation_rejected"
    ANSWER_EVALUATION_RERUN = "answer_evaluation_rerun"
    EXAM_RESULT_FINALIZED = "exam_result_finalized"
    EXAM_RESULT_APPROVED = "exam_result_approved"
    EXAM_RESULT_LOCKED = "exam_result_locked"
    EXAM_RESULT_UNLOCKED = "exam_result_unlocked"
    EXAM_RESULT_PUBLISHED = "exam_result_published"
    REPORT_GENERATED = "report_generated"
    NOTIFICATION_CREATED = "notification_created"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


REQUEST_ID_HEADER = "X-Request-ID"
