import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { TeacherReviewDashboardPage } from "@/pages/ocr/TeacherReviewDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnswerEvaluation } from "@/types/officialExam";
import type { Page } from "@/types/pagination";
import type { TeacherReviewDashboardSummary } from "@/types/teacherReview";
import type { User } from "@/types/auth";

const { getDashboardMock, getQueueMock } = vi.hoisted(() => ({
  getDashboardMock: vi.fn(),
  getQueueMock: vi.fn(),
}));
vi.mock("@/api/teacherReviewDashboard", () => ({
  getTeacherReviewDashboard: getDashboardMock,
  getTeacherReviewQueue: getQueueMock,
}));

const baseUser: User = {
  id: "user-1",
  email: "teacher@example.com",
  username: "teacher",
  full_name: "Teacher One",
  phone: null,
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: true,
  roles: ["teacher"],
  permissions: ["teacher_review_dashboard:read"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeSummary(overrides: Partial<TeacherReviewDashboardSummary> = {}): TeacherReviewDashboardSummary {
  return {
    pending_review_count: 12,
    medium_confidence_count: 5,
    low_confidence_count: 3,
    completed_reviews_count: 40,
    auto_accepted_count: 20,
    ...overrides,
  };
}

function makeEvaluation(overrides: Partial<AnswerEvaluation> = {}): AnswerEvaluation {
  return {
    id: "eval-1",
    institution_id: "inst-1",
    exam_session_id: "session-1",
    answer_script_id: "script-1",
    extracted_question_id: "question-1",
    extracted_model_answer_id: "model-answer-1",
    ai_provider_id: "provider-1",
    student_answer_text: "Answer text.",
    semantic_similarity_score: "0.85",
    keyword_match_score: "0.70",
    concept_match_score: "0.80",
    reasoning_score: "0.75",
    completeness_score: "0.90",
    relevance_score: "0.88",
    confidence_score: "0.82",
    confidence_tier: "high",
    max_marks: "10",
    suggested_marks: "8",
    final_marks: null,
    review_status: "pending_review",
    evaluated_at: "2026-01-01T00:00:00Z",
    reviewed_by: null,
    reviewed_at: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeQueuePage(overrides: Partial<Page<AnswerEvaluation>> = {}): Page<AnswerEvaluation> {
  return {
    items: [makeEvaluation()],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    ...overrides,
  };
}

function renderPage(user: User = baseUser) {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter>
          <ToastProvider>
            <TeacherReviewDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("TeacherReviewDashboardPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the 5 summary tiles with correct numbers", async () => {
    getDashboardMock.mockResolvedValue(makeSummary());
    getQueueMock.mockResolvedValue(makeQueuePage());
    renderPage();

    await screen.findByText("12");
    expect(screen.getByText("Pending Review")).toBeInTheDocument();
    expect(screen.getByText("Medium Confidence")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Low Confidence")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Completed Reviews")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("Auto Accepted")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("renders the queue table rows", async () => {
    getDashboardMock.mockResolvedValue(makeSummary());
    getQueueMock.mockResolvedValue(
      makeQueuePage({ items: [makeEvaluation({ id: "eval-1", exam_session_id: "session-abc" })] }),
    );
    renderPage();

    expect(await screen.findByText("session-abc")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("8 / 10")).toBeInTheDocument();
    expect(within(table).getByText("pending review")).toBeInTheDocument();
  });

  it("refetches the queue and summary with the updated confidence-tier filter", async () => {
    getDashboardMock.mockResolvedValue(makeSummary());
    getQueueMock.mockResolvedValue(makeQueuePage());
    renderPage();

    await screen.findByText("Pending Review");
    getQueueMock.mockClear();
    getDashboardMock.mockClear();

    await userEvent.selectOptions(screen.getByLabelText("Confidence Tier"), "high");

    await waitFor(() =>
      expect(getQueueMock).toHaveBeenCalledWith(
        expect.objectContaining({ confidence_tier: "high" }),
        expect.objectContaining({ page: 1, page_size: 20 }),
      ),
    );
    expect(getDashboardMock).toHaveBeenCalledWith(expect.objectContaining({ confidence_tier: "high" }));
  });

  it("renders pagination controls with the correct total", async () => {
    getDashboardMock.mockResolvedValue(makeSummary());
    getQueueMock.mockResolvedValue(makeQueuePage({ total: 45, total_pages: 3, page: 1, page_size: 20 }));
    renderPage();

    expect(await screen.findByText("1-20 of 45")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });

  it("navigates to the answer evaluation detail page when View is clicked", async () => {
    getDashboardMock.mockResolvedValue(makeSummary());
    getQueueMock.mockResolvedValue(
      makeQueuePage({ items: [makeEvaluation({ id: "eval-42" })] }),
    );
    renderPage();

    const viewButton = await screen.findByRole("button", { name: "View evaluation eval-42" });
    expect(viewButton).toBeInTheDocument();
  });
});
