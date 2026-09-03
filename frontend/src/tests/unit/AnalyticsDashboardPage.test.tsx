import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AnalyticsDashboardPage } from "@/pages/ocr/AnalyticsDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnalyticsOverview, QuestionWiseAnalytics } from "@/types/teacherReview";
import type { User } from "@/types/auth";

const { getOverviewMock, getQuestionWiseMock } = vi.hoisted(() => ({
  getOverviewMock: vi.fn(),
  getQuestionWiseMock: vi.fn(),
}));
vi.mock("@/api/analytics", () => ({
  getAnalyticsOverview: getOverviewMock,
  getQuestionWiseAnalytics: getQuestionWiseMock,
}));

const baseUser: User = {
  id: "user-1",
  email: "admin@example.com",
  username: "admin",
  full_name: "Admin",
  phone: null,
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: true,
  roles: ["institution_admin"],
  permissions: ["analytics:read"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeOverview(overrides: Partial<AnalyticsOverview> = {}): AnalyticsOverview {
  return {
    result_count: 42,
    average_marks: "72.50",
    highest_marks: "98.00",
    lowest_marks: "12.00",
    pass_percentage: "80",
    fail_percentage: "20",
    confidence_distribution: { high: 10, medium: 5, low: 2 },
    teacher_override_percentage: "15",
    average_ai_vs_teacher_difference: "1.25",
    ...overrides,
  };
}

function makeQuestionWise(): QuestionWiseAnalytics {
  return {
    questions: [
      {
        extracted_question_id: "q1",
        question_number: "1",
        evaluated_count: 20,
        max_marks: "10",
        average_marks: "8.00",
        average_ratio: "80.00",
      },
      {
        extracted_question_id: "q2",
        question_number: "2",
        evaluated_count: 18,
        max_marks: "10",
        average_marks: "5.00",
        average_ratio: "50.00",
      },
    ],
    most_difficult: [
      {
        extracted_question_id: "q2",
        question_number: "2",
        evaluated_count: 18,
        max_marks: "10",
        average_marks: "5.00",
        average_ratio: "50.00",
      },
    ],
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
            <AnalyticsDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AnalyticsDashboardPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders overview cards with the right numbers", async () => {
    getOverviewMock.mockResolvedValueOnce(makeOverview());
    renderPage();

    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("72.50")).toBeInTheDocument();
    expect(screen.getByText("98.00")).toBeInTheDocument();
    expect(screen.getByText("12.00")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("15%")).toBeInTheDocument();
    expect(screen.getByText("1.25")).toBeInTheDocument();
  });

  it("renders '—' for null numeric fields", async () => {
    getOverviewMock.mockResolvedValueOnce(
      makeOverview({
        average_marks: null,
        highest_marks: null,
        lowest_marks: null,
        pass_percentage: null,
        fail_percentage: null,
        teacher_override_percentage: null,
        average_ai_vs_teacher_difference: null,
      }),
    );
    renderPage();

    await screen.findByText("Marks Overview");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(7);
  });

  it("refetches the overview with the new filter value when a filter input changes", async () => {
    getOverviewMock.mockResolvedValue(makeOverview());
    renderPage();

    await waitFor(() =>
      expect(getOverviewMock).toHaveBeenCalledWith({
        exam_id: undefined,
        subject_id: undefined,
        course_id: undefined,
        department_id: undefined,
      }),
    );

    const examIdInput = screen.getByLabelText("Exam ID");
    fireEvent.change(examIdInput, { target: { value: "exam-123" } });

    await waitFor(() =>
      expect(getOverviewMock).toHaveBeenLastCalledWith({
        exam_id: "exam-123",
        subject_id: undefined,
        course_id: undefined,
        department_id: undefined,
      }),
    );
  });

  it("loads question-wise analytics for an exam id and renders both tables", async () => {
    getOverviewMock.mockResolvedValue(makeOverview());
    getQuestionWiseMock.mockResolvedValueOnce(makeQuestionWise());
    renderPage();

    await screen.findByText("Marks Overview");

    const examIdInputs = screen.getAllByLabelText(/^Exam ID/);
    const questionExamIdInput = examIdInputs[examIdInputs.length - 1];
    await userEvent.type(questionExamIdInput, "exam-456");
    await userEvent.click(screen.getByRole("button", { name: "Load" }));

    await waitFor(() => expect(getQuestionWiseMock).toHaveBeenCalledWith("exam-456"));

    expect(await screen.findByText("All Questions")).toBeInTheDocument();
    expect(screen.getByText("Most Difficult Questions")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getAllByText("2").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("8.00").length).toBe(1);
    expect(screen.getAllByText("5.00").length).toBe(2);
  });
});
