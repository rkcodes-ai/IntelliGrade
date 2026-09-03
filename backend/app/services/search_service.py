"""Global Search (Module 07, Feature 9).

Searches across Student (name/username/roll number), Teacher (name/
username), Subject, Question, and Evaluation (by the student's roll
number/name) — read-only `ILIKE` queries over existing tables, no new
search index. `StudentEnrollment.roll_number` is this codebase's closest
existing field to the brief's "Register Number"/"Hall Ticket" — no
separate columns exist for those, so this module reuses it rather than
adding new ones (see `KNOWN_LIMITATIONS.md`).
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer_evaluation import AnswerEvaluation
from app.models.exam_session import ExamSession
from app.models.extracted_question import ExtractedQuestion
from app.models.role import Role as RoleModel
from app.models.student_enrollment import StudentEnrollment
from app.models.subject import Subject
from app.models.user import User
from app.models.user_institution import UserInstitution
from app.models.user_role import UserRole
from app.schemas.search import SearchResultItem

#: Results returned per category, per search call.
_LIMIT_PER_CATEGORY = 10


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _users_with_role(
        self, institution_id: uuid.UUID, role_name: str, pattern: str
    ) -> list[SearchResultItem]:
        query = (
            select(User, StudentEnrollment.roll_number)
            .join(UserInstitution, UserInstitution.user_id == User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(RoleModel, RoleModel.id == UserRole.role_id)
            .outerjoin(StudentEnrollment, StudentEnrollment.student_user_id == User.id)
            .where(
                UserInstitution.institution_id == institution_id,
                RoleModel.name == role_name,
                User.deleted_at.is_(None),
                or_(
                    User.full_name.ilike(pattern),
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    StudentEnrollment.roll_number.ilike(pattern),
                ),
            )
            .limit(_LIMIT_PER_CATEGORY)
        )
        rows = (await self.session.execute(query)).all()
        seen: set[uuid.UUID] = set()
        items: list[SearchResultItem] = []
        for user, roll_number in rows:
            if user.id in seen:
                continue
            seen.add(user.id)
            subtitle = f"Roll No. {roll_number}" if roll_number else user.email
            items.append(
                SearchResultItem(
                    type="student" if role_name == "student" else "teacher",
                    id=user.id,
                    label=user.full_name,
                    subtitle=subtitle,
                )
            )
        return items

    async def _subjects(self, institution_id: uuid.UUID, pattern: str) -> list[SearchResultItem]:
        query = (
            select(Subject)
            .where(
                Subject.institution_id == institution_id,
                Subject.deleted_at.is_(None),
                or_(Subject.name.ilike(pattern), Subject.code.ilike(pattern)),
            )
            .limit(_LIMIT_PER_CATEGORY)
        )
        subjects = (await self.session.execute(query)).scalars().all()
        return [
            SearchResultItem(type="subject", id=s.id, label=s.name, subtitle=s.code)
            for s in subjects
        ]

    async def _questions(self, institution_id: uuid.UUID, pattern: str) -> list[SearchResultItem]:
        query = (
            select(ExtractedQuestion)
            .where(
                ExtractedQuestion.institution_id == institution_id,
                ExtractedQuestion.deleted_at.is_(None),
                or_(
                    ExtractedQuestion.question_text.ilike(pattern),
                    ExtractedQuestion.question_number.ilike(pattern),
                ),
            )
            .limit(_LIMIT_PER_CATEGORY)
        )
        questions = (await self.session.execute(query)).scalars().all()
        return [
            SearchResultItem(
                type="question",
                id=q.id,
                label=f"Q{q.question_number}",
                subtitle=(q.question_text or "")[:120],
            )
            for q in questions
        ]

    async def _evaluations(self, institution_id: uuid.UUID, pattern: str) -> list[SearchResultItem]:
        query = (
            select(AnswerEvaluation, User.full_name, StudentEnrollment.roll_number)
            .join(ExamSession, ExamSession.id == AnswerEvaluation.exam_session_id)
            .join(User, User.id == ExamSession.student_user_id)
            .outerjoin(StudentEnrollment, StudentEnrollment.student_user_id == User.id)
            .where(
                AnswerEvaluation.institution_id == institution_id,
                AnswerEvaluation.deleted_at.is_(None),
                or_(User.full_name.ilike(pattern), StudentEnrollment.roll_number.ilike(pattern)),
            )
            .limit(_LIMIT_PER_CATEGORY)
        )
        rows = (await self.session.execute(query)).all()
        return [
            SearchResultItem(
                type="evaluation",
                id=evaluation.id,
                label=f"Evaluation for {full_name}",
                subtitle=f"Roll No. {roll_number}" if roll_number else evaluation.review_status,
            )
            for evaluation, full_name, roll_number in rows
        ]

    async def search(self, institution_id: uuid.UUID, query_text: str) -> list[SearchResultItem]:
        pattern = f"%{query_text}%"
        results: list[SearchResultItem] = []
        results += await self._users_with_role(institution_id, "student", pattern)
        results += await self._users_with_role(institution_id, "teacher", pattern)
        results += await self._subjects(institution_id, pattern)
        results += await self._questions(institution_id, pattern)
        results += await self._evaluations(institution_id, pattern)
        return results
