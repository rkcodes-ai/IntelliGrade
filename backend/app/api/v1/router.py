"""
Aggregates all v1 endpoint routers into a single APIRouter.

Module 02 (IAM) adds `auth`, `users`, `roles`, `permissions`, `sessions`.
Module 03 (Academic Domain) adds `institutions` plus every other academic
entity router (see `docs/academic-domain-guide.md`).
Module 04 (Assessment Domain) adds `assessments` plus every question-bank/
question-paper/rubric/answer-key/exam entity router (see
`docs/assessment-domain-guide.md`).
Infra health/version endpoints live unversioned at the app root — see
`app/api/health.py`.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    academic_calendar,
    academic_statuses,
    academic_years,
    ai_configurations,
    ai_providers,
    ai_reference_answers,
    alternative_answers,
    analytics,
    answer_evaluations,
    answer_keys,
    answer_script_pages,
    answer_scripts,
    assessment_configurations,
    assessment_statuses,
    assessment_types,
    assessments,
    attendance_policies,
    auth,
    batches,
    bloom_taxonomy_levels,
    campuses,
    class_schedules,
    courses,
    departments,
    difficulty_levels,
    evaluation_configurations,
    evaluation_history,
    exam_instructions,
    exam_results,
    exam_schedules,
    exam_sessions,
    exams,
    expected_concepts,
    expected_keywords,
    extracted_model_answers,
    extracted_questions,
    grading_policies,
    institutions,
    mark_distributions,
    mark_scheme_ranges,
    model_answers,
    notifications,
    ocr_benchmark,
    ocr_configurations,
    ocr_jobs,
    ocr_providers,
    ocr_results,
    official_exam_document_pages,
    official_exam_documents,
    permissions,
    processing_history,
    programs,
    question_approvals,
    question_blueprint_sections,
    question_blueprints,
    question_categories,
    question_paper_question_mappings,
    question_paper_sections,
    question_paper_templates,
    question_paper_versions,
    question_papers,
    question_reviews,
    question_tags,
    question_types,
    question_versions,
    questions,
    randomization_strategies,
    reference_notes,
    reports,
    roles,
    rooms,
    rubric_criteria,
    rubrics,
    search,
    sections,
    semesters,
    sessions,
    student_enrollments,
    subject_allocations,
    subject_categories,
    subjects,
    teacher_assignments,
    teacher_review_dashboard,
    upload_jobs,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(permissions.router)
api_router.include_router(sessions.router)

api_router.include_router(institutions.router)
api_router.include_router(campuses.router)
api_router.include_router(departments.router)
api_router.include_router(programs.router)
api_router.include_router(courses.router)
api_router.include_router(academic_years.router)
api_router.include_router(semesters.router)
api_router.include_router(academic_calendar.router)
api_router.include_router(batches.router)
api_router.include_router(sections.router)
api_router.include_router(subject_categories.router)
api_router.include_router(subjects.router)
api_router.include_router(rooms.router)
api_router.include_router(subject_allocations.router)
api_router.include_router(teacher_assignments.router)
api_router.include_router(student_enrollments.router)
api_router.include_router(academic_statuses.router)
api_router.include_router(grading_policies.router)
api_router.include_router(attendance_policies.router)
api_router.include_router(class_schedules.router)

# --- Assessment Domain (Module 04) ---
api_router.include_router(assessment_types.router)
api_router.include_router(assessment_statuses.router)
api_router.include_router(assessments.router)
api_router.include_router(assessment_configurations.router)
api_router.include_router(evaluation_configurations.router)
api_router.include_router(question_categories.router)
api_router.include_router(question_types.router)
api_router.include_router(difficulty_levels.router)
api_router.include_router(bloom_taxonomy_levels.router)
api_router.include_router(question_tags.router)
api_router.include_router(questions.router)
api_router.include_router(question_paper_templates.router)
api_router.include_router(exams.router)
api_router.include_router(exam_instructions.router)
api_router.include_router(exam_schedules.router)
api_router.include_router(exam_sessions.router)
api_router.include_router(question_versions.router)
api_router.include_router(question_approvals.router)
api_router.include_router(question_reviews.router)
api_router.include_router(answer_keys.router)
api_router.include_router(model_answers.router)
api_router.include_router(alternative_answers.router)
api_router.include_router(reference_notes.router)
api_router.include_router(rubrics.router)
api_router.include_router(rubric_criteria.router)
api_router.include_router(mark_distributions.router)
api_router.include_router(expected_keywords.router)
api_router.include_router(expected_concepts.router)
api_router.include_router(question_blueprints.router)
api_router.include_router(question_blueprint_sections.router)
api_router.include_router(question_papers.router)
api_router.include_router(question_paper_versions.router)
api_router.include_router(question_paper_sections.router)
api_router.include_router(question_paper_question_mappings.router)
api_router.include_router(randomization_strategies.router)
api_router.include_router(evaluation_history.router)

# --- Answer Script OCR Pipeline (Module 05) ---
api_router.include_router(answer_scripts.router)
api_router.include_router(answer_script_pages.router)
api_router.include_router(upload_jobs.router)
api_router.include_router(ocr_providers.router)
api_router.include_router(ocr_benchmark.router)
api_router.include_router(ocr_configurations.router)
api_router.include_router(ocr_jobs.router)
api_router.include_router(ocr_results.router)
api_router.include_router(processing_history.router)

# --- Official Exam Content Ingestion & AI Evaluation (Module 06) ---
api_router.include_router(official_exam_documents.router)
api_router.include_router(official_exam_document_pages.router)
api_router.include_router(extracted_questions.router)
api_router.include_router(extracted_model_answers.router)
api_router.include_router(mark_scheme_ranges.router)
api_router.include_router(ai_providers.router)
api_router.include_router(ai_configurations.router)
api_router.include_router(ai_reference_answers.router)
api_router.include_router(answer_evaluations.router)

# --- Teacher Review, Result Finalization & Analytics (Module 07) ---
api_router.include_router(teacher_review_dashboard.router)
api_router.include_router(exam_results.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(search.router)
api_router.include_router(notifications.router)
