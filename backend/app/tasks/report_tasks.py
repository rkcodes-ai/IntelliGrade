"""Celery task driving background report generation (Module 07, Feature 8).
See ADR-045.

`report_type` selects WHAT data to export (resolved via `AnalyticsService`/
`TeacherReviewDashboardService`/direct queries, into a generic list of flat
row-dicts); `format` selects HOW to render those same rows (`reportlab` for
PDF, `openpyxl` for Excel, the stdlib `csv` module for CSV) — one generic
renderer per format, reused across every report type, rather than 7 x 3
bespoke renderers.
"""

import asyncio
import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import Task
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.exam_session import ExamSession
from app.models.report_job import ReportJob
from app.models.user import User
from app.repositories.exam_result_repository import ExamResultRepository
from app.schemas.analytics import AnalyticsFilters
from app.schemas.teacher_review import TeacherReviewFilters
from app.services.analytics_service import AnalyticsService
from app.services.storage_service import StorageService
from app.services.teacher_review_dashboard_service import TeacherReviewDashboardService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)

_EXTENSION_BY_FORMAT = {"pdf": "pdf", "excel": "xlsx", "csv": "csv"}
_CONTENT_TYPE_BY_FORMAT = {
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}
_REPORT_TITLES = {
    "student": "Student Report",
    "question_wise": "Question-wise Performance Report",
    "teacher_review": "Teacher Review Report",
    "ai_performance": "AI Performance Report",
    "institution_summary": "Institution Summary Report",
    "department_summary": "Department Summary Report",
    "course_summary": "Course Summary Report",
}


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    return uuid.UUID(str(value)) if value else None


async def _resolve_report_rows(
    session: AsyncSession,
    institution_id: uuid.UUID,
    report_type: str,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Every report type resolves to the same shape: a list of flat
    dicts, one per output row, column order taken from the first row's
    keys. This is what makes one PDF/Excel/CSV renderer per format work
    across all 7 report types."""
    analytics = AnalyticsService(session)
    filters = AnalyticsFilters(
        exam_id=_uuid_or_none(parameters.get("exam_id")),
        subject_id=_uuid_or_none(parameters.get("subject_id")),
        course_id=_uuid_or_none(parameters.get("course_id")),
        department_id=_uuid_or_none(parameters.get("department_id")),
    )

    if report_type == "question_wise":
        exam_id = _uuid_or_none(parameters.get("exam_id"))
        if exam_id is None:
            raise ValueError("question_wise report requires an 'exam_id' parameter.")
        data = await analytics.get_question_wise(institution_id, exam_id)
        return [
            {
                "Question": q.question_number,
                "Evaluated Count": q.evaluated_count,
                "Max Marks": q.max_marks,
                "Average Marks": q.average_marks,
                "Average Ratio": q.average_ratio,
            }
            for q in data.questions
        ]

    if report_type == "student":
        exam_session_id = _uuid_or_none(parameters.get("exam_session_id"))
        if exam_session_id is None:
            raise ValueError("student report requires an 'exam_session_id' parameter.")
        exam_session = await session.get(ExamSession, exam_session_id)
        student = (
            await session.get(User, exam_session.student_user_id)
            if exam_session is not None
            else None
        )
        result_repo = ExamResultRepository(session)
        exam_result = await result_repo.get_by_exam_session(institution_id, exam_session_id)
        return [
            {
                "Student": student.full_name if student is not None else "",
                "Status": exam_result.status if exam_result is not None else "not_finalized",
                "Total Marks": exam_result.total_marks if exam_result is not None else None,
                "Max Marks": exam_result.total_max_marks if exam_result is not None else None,
            }
        ]

    if report_type == "teacher_review":
        dashboard = TeacherReviewDashboardService(session)
        summary = await dashboard.get_dashboard_summary(
            institution_id,
            TeacherReviewFilters(
                exam_id=filters.exam_id,
                subject_id=filters.subject_id,
                course_id=filters.course_id,
                department_id=filters.department_id,
            ),
        )
        return [
            {
                "Pending Review": summary.pending_review_count,
                "Medium Confidence": summary.medium_confidence_count,
                "Low Confidence": summary.low_confidence_count,
                "Completed Reviews": summary.completed_reviews_count,
                "Auto Accepted": summary.auto_accepted_count,
            }
        ]

    overview = await analytics.get_overview(institution_id, filters)
    if report_type == "ai_performance":
        return [
            {
                "High Confidence Count": overview.confidence_distribution.high,
                "Medium Confidence Count": overview.confidence_distribution.medium,
                "Low Confidence Count": overview.confidence_distribution.low,
                "Teacher Override %": overview.teacher_override_percentage,
                "Avg AI vs Teacher Difference": overview.average_ai_vs_teacher_difference,
            }
        ]

    # institution_summary / department_summary / course_summary
    return [
        {
            "Result Count": overview.result_count,
            "Average Marks": overview.average_marks,
            "Highest Marks": overview.highest_marks,
            "Lowest Marks": overview.lowest_marks,
            "Pass %": overview.pass_percentage,
            "Fail %": overview.fail_percentage,
        }
    ]


def _render_pdf(title: str, rows: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list[Any] = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    if rows:
        headers = list(rows[0].keys())
        data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]
        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        elements.append(table)
    else:
        elements.append(Paragraph("No data available for this report.", styles["Normal"]))
    doc.build(elements)
    return buffer.getvalue()


def _render_excel(title: str, rows: list[dict[str, Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31] if title else "Report"
    if rows:
        headers = list(rows[0].keys())
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(h) for h in headers])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _render_csv(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _render(format_: str, title: str, rows: list[dict[str, Any]]) -> bytes:
    if format_ == "pdf":
        return _render_pdf(title, rows)
    if format_ == "excel":
        return _render_excel(title, rows)
    return _render_csv(rows)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="report.generate",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=120,
)
def generate_report_task(self: Task, report_job_id: str) -> None:
    """Entry point enqueued after a successful `POST /reports` — see
    `app/api/v1/endpoints/reports.py`."""
    try:
        asyncio.run(_run_report_generation(report_job_id))
    except Exception as exc:  # noqa: BLE001 - Celery retry needs the original exception
        logger.error("report_generation_failed", report_job_id=report_job_id, error=str(exc))
        raise self.retry(exc=exc) from exc


async def _run_report_generation(report_job_id: str) -> None:
    job_id = uuid.UUID(report_job_id)

    async with AsyncSessionLocal() as session:
        job = await session.get(ReportJob, job_id)
        if job is None:
            return

        job.status = "processing"
        job.started_at = datetime.now(UTC)
        await session.commit()

        try:
            title = _REPORT_TITLES.get(job.report_type, job.report_type)
            rows = await _resolve_report_rows(
                session, job.institution_id, job.report_type, job.parameters or {}
            )
            content = _render(job.format, title, rows)

            extension = _EXTENSION_BY_FORMAT[job.format]
            content_type = _CONTENT_TYPE_BY_FORMAT[job.format]
            storage_key = f"reports/{job.institution_id}/{job.id}/{job.report_type}.{extension}"
            storage = StorageService()
            await storage.put_bytes(storage_key, content, content_type)

            job.storage_key = storage_key
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            await session.commit()
        except Exception as exc:
            job.status = "failed"
            job.failure_reason = str(exc)
            await session.commit()
            raise
