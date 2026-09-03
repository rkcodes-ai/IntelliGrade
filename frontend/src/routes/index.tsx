import { lazy, Suspense, type JSX } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { DashboardHomePage } from "@/pages/DashboardHomePage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { SessionsPage } from "@/pages/SessionsPage";
import { UnauthorizedPage } from "@/pages/UnauthorizedPage";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGuard } from "@/routes/guards/PermissionGuard";
import { ProtectedRoute } from "@/routes/guards/ProtectedRoute";

// The 11 Academic Domain (Module 03) screens are lazy-loaded and
// route-split — together they're a large fraction of the app's bundle,
// and most users only ever touch a handful of them per session.
const InstitutionsPage = lazy(() =>
  import("@/pages/academic/InstitutionsPage").then((m) => ({ default: m.InstitutionsPage })),
);
const CampusesPage = lazy(() =>
  import("@/pages/academic/CampusesPage").then((m) => ({ default: m.CampusesPage })),
);
const DepartmentsPage = lazy(() =>
  import("@/pages/academic/DepartmentsPage").then((m) => ({ default: m.DepartmentsPage })),
);
const ProgramsPage = lazy(() =>
  import("@/pages/academic/ProgramsPage").then((m) => ({ default: m.ProgramsPage })),
);
const CoursesPage = lazy(() =>
  import("@/pages/academic/CoursesPage").then((m) => ({ default: m.CoursesPage })),
);
const AcademicYearsPage = lazy(() =>
  import("@/pages/academic/AcademicYearsPage").then((m) => ({ default: m.AcademicYearsPage })),
);
const SemestersPage = lazy(() =>
  import("@/pages/academic/SemestersPage").then((m) => ({ default: m.SemestersPage })),
);
const SectionsPage = lazy(() =>
  import("@/pages/academic/SectionsPage").then((m) => ({ default: m.SectionsPage })),
);
const SubjectsPage = lazy(() =>
  import("@/pages/academic/SubjectsPage").then((m) => ({ default: m.SubjectsPage })),
);
const TeacherAssignmentsPage = lazy(() =>
  import("@/pages/academic/TeacherAssignmentsPage").then((m) => ({
    default: m.TeacherAssignmentsPage,
  })),
);
const StudentEnrollmentsPage = lazy(() =>
  import("@/pages/academic/StudentEnrollmentsPage").then((m) => ({
    default: m.StudentEnrollmentsPage,
  })),
);

// The 12 Assessment Domain (Module 04) screens follow the same
// lazy-loaded/code-split, `PermissionGuard`-per-route convention as Module
// 03 above.
const AssessmentDashboardPage = lazy(() =>
  import("@/pages/assessment/AssessmentDashboardPage").then((m) => ({
    default: m.AssessmentDashboardPage,
  })),
);
const ExamManagementPage = lazy(() =>
  import("@/pages/assessment/ExamManagementPage").then((m) => ({ default: m.ExamManagementPage })),
);
const ExamSchedulePage = lazy(() =>
  import("@/pages/assessment/ExamSchedulePage").then((m) => ({ default: m.ExamSchedulePage })),
);
const BlueprintBuilderPage = lazy(() =>
  import("@/pages/assessment/BlueprintBuilderPage").then((m) => ({
    default: m.BlueprintBuilderPage,
  })),
);
const QuestionBankDashboardPage = lazy(() =>
  import("@/pages/assessment/QuestionBankDashboardPage").then((m) => ({
    default: m.QuestionBankDashboardPage,
  })),
);
const QuestionEditorPage = lazy(() =>
  import("@/pages/assessment/QuestionEditorPage").then((m) => ({ default: m.QuestionEditorPage })),
);
const QuestionViewerPage = lazy(() =>
  import("@/pages/assessment/QuestionViewerPage").then((m) => ({ default: m.QuestionViewerPage })),
);
const QuestionReviewScreenPage = lazy(() =>
  import("@/pages/assessment/QuestionReviewScreenPage").then((m) => ({
    default: m.QuestionReviewScreenPage,
  })),
);
const QuestionApprovalScreenPage = lazy(() =>
  import("@/pages/assessment/QuestionApprovalScreenPage").then((m) => ({
    default: m.QuestionApprovalScreenPage,
  })),
);
const QuestionPaperBuilderPage = lazy(() =>
  import("@/pages/assessment/QuestionPaperBuilderPage").then((m) => ({
    default: m.QuestionPaperBuilderPage,
  })),
);
const RubricBuilderPage = lazy(() =>
  import("@/pages/assessment/RubricBuilderPage").then((m) => ({ default: m.RubricBuilderPage })),
);
const AnswerKeyBuilderPage = lazy(() =>
  import("@/pages/assessment/AnswerKeyBuilderPage").then((m) => ({
    default: m.AnswerKeyBuilderPage,
  })),
);

// The 10 Answer Script OCR Pipeline (Module 05) screens follow the same
// lazy-loaded/code-split, `PermissionGuard`-per-route convention as
// Modules 03/04 above.
const AnswerScriptUploadDashboardPage = lazy(() =>
  import("@/pages/ocr/AnswerScriptUploadDashboardPage").then((m) => ({
    default: m.AnswerScriptUploadDashboardPage,
  })),
);
const UploadQueuePage = lazy(() =>
  import("@/pages/ocr/UploadQueuePage").then((m) => ({ default: m.UploadQueuePage })),
);
const OCRStatusDashboardPage = lazy(() =>
  import("@/pages/ocr/OCRStatusDashboardPage").then((m) => ({
    default: m.OCRStatusDashboardPage,
  })),
);
const AnswerScriptViewerPage = lazy(() =>
  import("@/pages/ocr/AnswerScriptViewerPage").then((m) => ({
    default: m.AnswerScriptViewerPage,
  })),
);
const PageViewerPage = lazy(() =>
  import("@/pages/ocr/PageViewerPage").then((m) => ({ default: m.PageViewerPage })),
);
const OCRTextViewerPage = lazy(() =>
  import("@/pages/ocr/OCRTextViewerPage").then((m) => ({ default: m.OCRTextViewerPage })),
);
const ProcessingHistoryPage = lazy(() =>
  import("@/pages/ocr/ProcessingHistoryPage").then((m) => ({ default: m.ProcessingHistoryPage })),
);
const OCRJobDetailsPage = lazy(() =>
  import("@/pages/ocr/OCRJobDetailsPage").then((m) => ({ default: m.OCRJobDetailsPage })),
);
const OCRProviderManagementPage = lazy(() =>
  import("@/pages/ocr/OCRProviderManagementPage").then((m) => ({
    default: m.OCRProviderManagementPage,
  })),
);
const OCRConfigurationPage = lazy(() =>
  import("@/pages/ocr/OCRConfigurationPage").then((m) => ({ default: m.OCRConfigurationPage })),
);

// The 9 Official Exam Content Ingestion & AI Evaluation (Module 06)
// screens follow the same lazy-loaded/code-split, `PermissionGuard`-per-
// route convention as Modules 03/04/05 above.
const OfficialDocumentUploadDashboardPage = lazy(() =>
  import("@/pages/ocr/OfficialDocumentUploadDashboardPage").then((m) => ({
    default: m.OfficialDocumentUploadDashboardPage,
  })),
);
const OfficialExamDocumentDetailPage = lazy(() =>
  import("@/pages/ocr/OfficialExamDocumentDetailPage").then((m) => ({
    default: m.OfficialExamDocumentDetailPage,
  })),
);
const QuestionVerificationPage = lazy(() =>
  import("@/pages/ocr/QuestionVerificationPage").then((m) => ({
    default: m.QuestionVerificationPage,
  })),
);
const ModelAnswerVerificationPage = lazy(() =>
  import("@/pages/ocr/ModelAnswerVerificationPage").then((m) => ({
    default: m.ModelAnswerVerificationPage,
  })),
);
const MarkSchemeVerificationPage = lazy(() =>
  import("@/pages/ocr/MarkSchemeVerificationPage").then((m) => ({
    default: m.MarkSchemeVerificationPage,
  })),
);
const AIProviderManagementPage = lazy(() =>
  import("@/pages/ocr/AIProviderManagementPage").then((m) => ({
    default: m.AIProviderManagementPage,
  })),
);
const AIConfigurationPage = lazy(() =>
  import("@/pages/ocr/AIConfigurationPage").then((m) => ({ default: m.AIConfigurationPage })),
);
const EvaluationReviewDashboardPage = lazy(() =>
  import("@/pages/ocr/EvaluationReviewDashboardPage").then((m) => ({
    default: m.EvaluationReviewDashboardPage,
  })),
);
const AnswerEvaluationDetailPage = lazy(() =>
  import("@/pages/ocr/AnswerEvaluationDetailPage").then((m) => ({
    default: m.AnswerEvaluationDetailPage,
  })),
);
const AIReferenceAnswerReviewPage = lazy(() =>
  import("@/pages/ocr/AIReferenceAnswerReviewPage").then((m) => ({
    default: m.AIReferenceAnswerReviewPage,
  })),
);
const AIReferenceAnswerDashboardPage = lazy(() =>
  import("@/pages/ocr/AIReferenceAnswerDashboardPage").then((m) => ({
    default: m.AIReferenceAnswerDashboardPage,
  })),
);

// Teacher Review, Result Finalization & Analytics (Module 07) — same
// lazy-loaded/code-split, `PermissionGuard`-per-route convention as
// Modules 03-06.
const TeacherReviewDashboardPage = lazy(() =>
  import("@/pages/ocr/TeacherReviewDashboardPage").then((m) => ({
    default: m.TeacherReviewDashboardPage,
  })),
);
const ResultFinalizationPage = lazy(() =>
  import("@/pages/ocr/ResultFinalizationPage").then((m) => ({
    default: m.ResultFinalizationPage,
  })),
);
const AnalyticsDashboardPage = lazy(() =>
  import("@/pages/ocr/AnalyticsDashboardPage").then((m) => ({
    default: m.AnalyticsDashboardPage,
  })),
);
const ReportsPage = lazy(() =>
  import("@/pages/ocr/ReportsPage").then((m) => ({ default: m.ReportsPage })),
);
const GlobalSearchPage = lazy(() =>
  import("@/pages/ocr/GlobalSearchPage").then((m) => ({ default: m.GlobalSearchPage })),
);
const NotificationsPage = lazy(() =>
  import("@/pages/ocr/NotificationsPage").then((m) => ({ default: m.NotificationsPage })),
);

function withSuspense(element: JSX.Element) {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center p-10">
          <Spinner />
        </div>
      }
    >
      {element}
    </Suspense>
  );
}

import { DatasetBenchmarkDemoPage } from "@/pages/DatasetBenchmarkDemoPage";

/**
 * Route tree. `RoleGuard` / `PermissionGuard` (see `routes/guards/`) gate
 * role- or permission-scoped access. The Academic Domain (Module 03)
 * screens below are the first routes to use `PermissionGuard`, each gated
 * on that entity's own `:read` permission code (create/update/delete are
 * further gated per-action inside each page component), and are lazy-
 * loaded/code-split for bundle size.
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/dataset-demo",
    element: <DatasetBenchmarkDemoPage />,
  },
  {
    element: <AuthLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
    ],
  },
  {
    path: "/unauthorized",
    element: <UnauthorizedPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/dashboard",
        element: <DashboardLayout />,
        children: [
          { index: true, element: <DashboardHomePage /> },
          { path: "profile", element: <ProfilePage /> },
          { path: "sessions", element: <SessionsPage /> },
          {
            element: <PermissionGuard requiredPermissions={["institutions:read"]} />,
            children: [{ path: "institutions", element: withSuspense(<InstitutionsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["campuses:read"]} />,
            children: [{ path: "campuses", element: withSuspense(<CampusesPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["departments:read"]} />,
            children: [{ path: "departments", element: withSuspense(<DepartmentsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["programs:read"]} />,
            children: [{ path: "programs", element: withSuspense(<ProgramsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["courses:read"]} />,
            children: [{ path: "courses", element: withSuspense(<CoursesPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["academic_years:read"]} />,
            children: [{ path: "academic-years", element: withSuspense(<AcademicYearsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["semesters:read"]} />,
            children: [{ path: "semesters", element: withSuspense(<SemestersPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["sections:read"]} />,
            children: [{ path: "sections", element: withSuspense(<SectionsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["subjects:read"]} />,
            children: [{ path: "subjects", element: withSuspense(<SubjectsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["teacher_assignments:read"]} />,
            children: [{ path: "teacher-assignments", element: withSuspense(<TeacherAssignmentsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["student_enrollments:read"]} />,
            children: [{ path: "student-enrollments", element: withSuspense(<StudentEnrollmentsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["assessments:read"]} />,
            children: [{ path: "assessments", element: withSuspense(<AssessmentDashboardPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["exams:read"]} />,
            children: [{ path: "exams", element: withSuspense(<ExamManagementPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["exam_schedules:read"]} />,
            children: [{ path: "exam-schedules", element: withSuspense(<ExamSchedulePage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["question_blueprints:read"]} />,
            children: [{ path: "question-blueprints", element: withSuspense(<BlueprintBuilderPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["questions:read"]} />,
            children: [
              { path: "questions", element: withSuspense(<QuestionBankDashboardPage />) },
              { path: "questions/:id", element: withSuspense(<QuestionViewerPage />) },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["questions:create"]} />,
            children: [{ path: "questions/new", element: withSuspense(<QuestionEditorPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["questions:update"]} />,
            children: [{ path: "questions/:id/edit", element: withSuspense(<QuestionEditorPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["question_reviews:read"]} />,
            children: [
              { path: "questions/:id/reviews", element: withSuspense(<QuestionReviewScreenPage />) },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["questions:approve"]} />,
            children: [
              { path: "question-approvals", element: withSuspense(<QuestionApprovalScreenPage />) },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["question_papers:read"]} />,
            children: [{ path: "question-papers", element: withSuspense(<QuestionPaperBuilderPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["rubrics:read"]} />,
            children: [{ path: "rubrics", element: withSuspense(<RubricBuilderPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["answer_keys:read"]} />,
            children: [{ path: "answer-keys", element: withSuspense(<AnswerKeyBuilderPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["answer_scripts:read"]} />,
            children: [
              { path: "answer-scripts", element: withSuspense(<AnswerScriptUploadDashboardPage />) },
              { path: "answer-scripts/:id", element: withSuspense(<AnswerScriptViewerPage />) },
              {
                path: "answer-scripts/:scriptId/history",
                element: withSuspense(<ProcessingHistoryPage />),
              },
              {
                path: "answer-scripts/:scriptId/pages/:pageId",
                element: withSuspense(<PageViewerPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["upload_jobs:read"]} />,
            children: [{ path: "upload-queue", element: withSuspense(<UploadQueuePage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["ocr_jobs:read"]} />,
            children: [
              { path: "ocr-status", element: withSuspense(<OCRStatusDashboardPage />) },
              { path: "ocr-jobs/:id", element: withSuspense(<OCRJobDetailsPage />) },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["ocr_results:read"]} />,
            children: [{ path: "ocr-results/:id", element: withSuspense(<OCRTextViewerPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["ocr_providers:read"]} />,
            children: [
              { path: "ocr-providers", element: withSuspense(<OCRProviderManagementPage />) },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["ocr_configurations:read"]} />,
            children: [
              { path: "ocr-configurations", element: withSuspense(<OCRConfigurationPage />) },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["official_exam_documents:read"]} />,
            children: [
              {
                path: "official-exam-documents",
                element: withSuspense(<OfficialDocumentUploadDashboardPage />),
              },
              {
                path: "official-exam-documents/:id",
                element: withSuspense(<OfficialExamDocumentDetailPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["extracted_questions:read"]} />,
            children: [
              {
                path: "official-exam-documents/:documentId/questions",
                element: withSuspense(<QuestionVerificationPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["extracted_model_answers:read"]} />,
            children: [
              {
                path: "official-exam-documents/:documentId/model-answers",
                element: withSuspense(<ModelAnswerVerificationPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["mark_scheme_ranges:read"]} />,
            children: [
              {
                path: "official-exam-documents/:documentId/mark-scheme",
                element: withSuspense(<MarkSchemeVerificationPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["ai_providers:read"]} />,
            children: [{ path: "ai-providers", element: withSuspense(<AIProviderManagementPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["ai_configurations:read"]} />,
            children: [{ path: "ai-configurations", element: withSuspense(<AIConfigurationPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["answer_evaluations:read"]} />,
            children: [
              {
                path: "answer-evaluations",
                element: withSuspense(<EvaluationReviewDashboardPage />),
              },
              {
                path: "answer-evaluations/:id",
                element: withSuspense(<AnswerEvaluationDetailPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["ai_reference_answers:read"]} />,
            children: [
              {
                path: "ai-reference-answers",
                element: withSuspense(<AIReferenceAnswerDashboardPage />),
              },
              {
                path: "extracted-questions/:extractedQuestionId/ai-reference-answer",
                element: withSuspense(<AIReferenceAnswerReviewPage />),
              },
            ],
          },
          {
            element: (
              <PermissionGuard requiredPermissions={["teacher_review_dashboard:read"]} />
            ),
            children: [
              {
                path: "teacher-review",
                element: withSuspense(<TeacherReviewDashboardPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["exam_results:read"]} />,
            children: [
              {
                path: "exam-results",
                element: withSuspense(<ResultFinalizationPage />),
              },
            ],
          },
          {
            element: <PermissionGuard requiredPermissions={["analytics:read"]} />,
            children: [{ path: "analytics", element: withSuspense(<AnalyticsDashboardPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["reports:read"]} />,
            children: [{ path: "reports", element: withSuspense(<ReportsPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["search:read"]} />,
            children: [{ path: "search", element: withSuspense(<GlobalSearchPage />) }],
          },
          {
            element: <PermissionGuard requiredPermissions={["notifications:read"]} />,
            children: [{ path: "notifications", element: withSuspense(<NotificationsPage />) }],
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
