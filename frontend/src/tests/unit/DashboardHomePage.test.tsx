import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardHomePage } from "@/pages/DashboardHomePage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnalyticsOverview } from "@/types/teacherReview";
import type { OCRJob } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  fetchHealthStatusMock,
  getAnalyticsOverviewMock,
  getTeacherReviewDashboardMock,
  getTeacherReviewQueueMock,
  listOCRJobsMock,
  listUploadJobsMock,
  listReportsMock,
  listMyNotificationsMock,
  listMyInstitutionsMock,
} = vi.hoisted(() => ({
  fetchHealthStatusMock: vi.fn(),
  getAnalyticsOverviewMock: vi.fn(),
  getTeacherReviewDashboardMock: vi.fn(),
  getTeacherReviewQueueMock: vi.fn(),
  listOCRJobsMock: vi.fn(),
  listUploadJobsMock: vi.fn(),
  listReportsMock: vi.fn(),
  listMyNotificationsMock: vi.fn(),
  listMyInstitutionsMock: vi.fn(),
}));

vi.mock("@/api/health", () => ({ fetchHealthStatus: fetchHealthStatusMock }));
vi.mock("@/api/analytics", () => ({ getAnalyticsOverview: getAnalyticsOverviewMock }));
vi.mock("@/api/teacherReviewDashboard", () => ({
  getTeacherReviewDashboard: getTeacherReviewDashboardMock,
  getTeacherReviewQueue: getTeacherReviewQueueMock,
}));
vi.mock("@/api/ocrJobs", () => ({ listOCRJobs: listOCRJobsMock }));
vi.mock("@/api/uploadJobs", () => ({ listUploadJobs: listUploadJobsMock }));
vi.mock("@/api/reports", () => ({ listReports: listReportsMock }));
vi.mock("@/api/notifications", () => ({ listMyNotifications: listMyNotificationsMock }));
vi.mock("@/api/institutions", () => ({ listMyInstitutions: listMyInstitutionsMock }));

const FULL_PERMISSIONS = [
  "teacher_review_dashboard:read",
  "ocr_jobs:read",
  "analytics:read",
  "upload_jobs:read",
  "reports:read",
  "notifications:read",
  "official_exam_documents:create",
  "answer_scripts:create",
];

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    email: "admin@example.com",
    username: "admin",
    full_name: "Ada Lovelace",
    phone: null,
    avatar_url: null,
    timezone: "UTC",
    language: "en",
    preferences: {},
    is_active: true,
    is_verified: true,
    roles: ["institution_admin"],
    permissions: FULL_PERMISSIONS,
    last_login_at: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderDashboard(user: User) {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardHomePage />
        </MemoryRouter>
      </QueryClientProvider>
    </Provider>,
  );
}

function emptyPage<T>(items: T[] = []): Page<T> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function makeOcrJob(overrides: Partial<OCRJob> = {}): OCRJob {
  return {
    id: "job-1",
    institution_id: "inst-1",
    answer_script_id: "script-12345678",
    ocr_provider_id: "provider-1",
    requested_ocr_provider_id: null,
    fallback_reason: null,
    celery_task_id: null,
    status: "queued",
    priority: 0,
    retry_count: 0,
    max_retries: 3,
    started_at: null,
    completed_at: null,
    error_message: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeAnalyticsOverview(overrides: Partial<AnalyticsOverview> = {}): AnalyticsOverview {
  return {
    result_count: 42,
    average_marks: "72.50",
    highest_marks: "98.00",
    lowest_marks: "12.00",
    pass_percentage: "80",
    fail_percentage: "20",
    confidence_distribution: { high: 8, medium: 3, low: 1 },
    teacher_override_percentage: "15",
    average_ai_vs_teacher_difference: "1.25",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default resolved values keep every widget's happy path exercised even
  // when a given test doesn't care about a particular widget.
  fetchHealthStatusMock.mockResolvedValue({ status: "ok", environment: "test" });
  getAnalyticsOverviewMock.mockResolvedValue(makeAnalyticsOverview());
  getTeacherReviewDashboardMock.mockResolvedValue({
    pending_review_count: 7,
    medium_confidence_count: 2,
    low_confidence_count: 1,
    completed_reviews_count: 20,
    auto_accepted_count: 5,
  });
  getTeacherReviewQueueMock.mockResolvedValue(emptyPage());
  listOCRJobsMock.mockResolvedValue(emptyPage([makeOcrJob()]));
  listUploadJobsMock.mockResolvedValue(emptyPage());
  listReportsMock.mockResolvedValue(emptyPage());
  listMyNotificationsMock.mockResolvedValue([]);
  listMyInstitutionsMock.mockResolvedValue([
    { id: "inst-1", name: "IntelliGrade QA Institute", code: "QA" },
  ]);
});

describe("DashboardHomePage", () => {
  it("greets the signed-in user by name", async () => {
    renderDashboard(makeUser());
    expect(await screen.findByText(/Ada Lovelace/)).toBeInTheDocument();
  });

  it("renders real KPI values from the mocked API responses", async () => {
    renderDashboard(makeUser());
    expect(await screen.findByText("Pending Reviews")).toBeInTheDocument();
    expect(await screen.findByText("7")).toBeInTheDocument(); // pending_review_count
    expect(await screen.findByText("Operational")).toBeInTheDocument(); // system health
  });

  it("renders the Analytics section with confidence distribution data", async () => {
    renderDashboard(makeUser());
    expect(await screen.findByText("Confidence Distribution")).toBeInTheDocument();
    expect(await screen.findByText("Pass / Fail Rate")).toBeInTheDocument();
  });

  it("hides every gated widget and shows a fallback message for a permission-less user", async () => {
    renderDashboard(makeUser({ permissions: [] }));
    expect(await screen.findByText("Welcome to IntelliGrade")).toBeInTheDocument();
    expect(screen.queryByText("Pending Reviews")).not.toBeInTheDocument();
    expect(screen.queryByText("OCR Queue")).not.toBeInTheDocument();
  });

  it("still shows System Health for a permission-less user (no permission required)", async () => {
    renderDashboard(makeUser({ permissions: [] }));
    expect(await screen.findByText("System Health")).toBeInTheDocument();
  });
});
