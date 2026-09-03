"""
ORM models (SQLAlchemy 2.x).

Every model module is imported here so that (a) `Base.metadata` sees every
table for Alembic autogeneration, and (b) string-based `relationship()`
forward references (e.g. `Mapped[list["UserRole"]]`) resolve correctly
regardless of import order elsewhere in the app.
"""

from app.models.academic_calendar_event import AcademicCalendarEvent
from app.models.academic_status import AcademicStatus
from app.models.academic_year import AcademicYear
from app.models.ai_configuration import AIConfiguration
from app.models.ai_provider import AIProvider
from app.models.ai_reference_answer import AIReferenceAnswer
from app.models.alternative_answer import AlternativeAnswer
from app.models.answer_evaluation import AnswerEvaluation
from app.models.answer_key import AnswerKey
from app.models.answer_script import AnswerScript
from app.models.answer_script_page import AnswerScriptPage
from app.models.assessment import Assessment
from app.models.assessment_configuration import AssessmentConfiguration
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.attendance_policy import AttendancePolicy
from app.models.audit_log import AuditLog
from app.models.batch import Batch
from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.models.campus import Campus
from app.models.class_schedule import ClassSchedule
from app.models.course import Course
from app.models.department import Department
from app.models.difficulty_level import DifficultyLevel
from app.models.document_region import DocumentRegion
from app.models.evaluation_configuration import EvaluationConfiguration
from app.models.evaluation_history import EvaluationHistory
from app.models.exam import Exam
from app.models.exam_instructions import ExamInstructions
from app.models.exam_result import ExamResult
from app.models.exam_schedule import ExamSchedule
from app.models.exam_session import ExamSession
from app.models.expected_concept import ExpectedConcept
from app.models.expected_keyword import ExpectedKeyword
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.grading_policy import GradingPolicy
from app.models.institution import Institution
from app.models.mark_distribution import MarkDistribution
from app.models.mark_scheme_range import MarkSchemeRange
from app.models.model_answer import ModelAnswer
from app.models.notification_event import NotificationEvent
from app.models.ocr_block import OCRBlock
from app.models.ocr_configuration import OCRConfiguration
from app.models.ocr_job import OCRJob
from app.models.ocr_line import OCRLine
from app.models.ocr_provider import OCRProvider
from app.models.ocr_provider_candidate import OCRProviderCandidate
from app.models.ocr_result import OCRResult
from app.models.ocr_word import OCRWord
from app.models.official_exam_document import OfficialExamDocument
from app.models.official_exam_document_page import OfficialExamDocumentPage
from app.models.password_history import PasswordHistory
from app.models.password_reset_token import PasswordResetToken
from app.models.permission import Permission
from app.models.processing_history import ProcessingHistory
from app.models.program import Program
from app.models.question import Question
from app.models.question_approval import QuestionApproval
from app.models.question_blueprint import QuestionBlueprint
from app.models.question_blueprint_section import QuestionBlueprintSection
from app.models.question_category import QuestionCategory
from app.models.question_paper import QuestionPaper
from app.models.question_paper_question_mapping import QuestionPaperQuestionMapping
from app.models.question_paper_section import QuestionPaperSection
from app.models.question_paper_template import QuestionPaperTemplate
from app.models.question_paper_version import QuestionPaperVersion
from app.models.question_review import QuestionReview
from app.models.question_tag import QuestionTag
from app.models.question_tag_map import QuestionTagMap
from app.models.question_type import QuestionType
from app.models.question_version import QuestionVersion
from app.models.randomization_strategy import RandomizationStrategy
from app.models.reference_note import ReferenceNote
from app.models.refresh_token import RefreshToken
from app.models.report_job import ReportJob
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.room import Room
from app.models.rubric import Rubric
from app.models.rubric_criterion import RubricCriterion
from app.models.section import Section
from app.models.semester import Semester
from app.models.session import Session
from app.models.student_enrollment import StudentEnrollment
from app.models.subject import Subject
from app.models.subject_allocation import SubjectAllocation
from app.models.subject_category import SubjectCategory
from app.models.teacher_assignment import TeacherAssignment
from app.models.upload_job import UploadJob
from app.models.user import User
from app.models.user_institution import UserInstitution
from app.models.user_role import UserRole

__all__ = [
    "AcademicCalendarEvent",
    "AcademicStatus",
    "AcademicYear",
    "AIConfiguration",
    "AIProvider",
    "AIReferenceAnswer",
    "AlternativeAnswer",
    "AnswerEvaluation",
    "AnswerKey",
    "AnswerScript",
    "AnswerScriptPage",
    "Assessment",
    "AssessmentConfiguration",
    "AssessmentStatus",
    "AssessmentType",
    "AttendancePolicy",
    "AuditLog",
    "Batch",
    "BloomTaxonomyLevel",
    "Campus",
    "ClassSchedule",
    "Course",
    "Department",
    "DifficultyLevel",
    "DocumentRegion",
    "EvaluationConfiguration",
    "EvaluationHistory",
    "Exam",
    "ExamInstructions",
    "ExamResult",
    "ExamSchedule",
    "ExamSession",
    "ExpectedConcept",
    "ExpectedKeyword",
    "ExtractedModelAnswer",
    "ExtractedQuestion",
    "GradingPolicy",
    "Institution",
    "MarkDistribution",
    "MarkSchemeRange",
    "ModelAnswer",
    "NotificationEvent",
    "OCRBlock",
    "OCRConfiguration",
    "OCRJob",
    "OCRLine",
    "OCRProvider",
    "OCRProviderCandidate",
    "OCRResult",
    "OCRWord",
    "OfficialExamDocument",
    "OfficialExamDocumentPage",
    "PasswordHistory",
    "PasswordResetToken",
    "Permission",
    "ProcessingHistory",
    "Program",
    "Question",
    "QuestionApproval",
    "QuestionBlueprint",
    "QuestionBlueprintSection",
    "QuestionCategory",
    "QuestionPaper",
    "QuestionPaperQuestionMapping",
    "QuestionPaperSection",
    "QuestionPaperTemplate",
    "QuestionPaperVersion",
    "QuestionReview",
    "QuestionTag",
    "QuestionTagMap",
    "QuestionType",
    "QuestionVersion",
    "RandomizationStrategy",
    "ReferenceNote",
    "RefreshToken",
    "ReportJob",
    "Role",
    "RolePermission",
    "Room",
    "Rubric",
    "RubricCriterion",
    "Section",
    "Semester",
    "Session",
    "StudentEnrollment",
    "Subject",
    "SubjectAllocation",
    "SubjectCategory",
    "TeacherAssignment",
    "UploadJob",
    "User",
    "UserInstitution",
    "UserRole",
]
