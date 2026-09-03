import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { EvaluationReviewDashboardPage } from "@/pages/ocr/EvaluationReviewDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnswerEvaluation } from "@/types/officialExam";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, triggerMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  triggerMock: vi.fn(),
}));
vi.mock("@/api/answerEvaluations", () => ({
  listAnswerEvaluations: listMock,
  triggerAnswerEvaluation: triggerMock,
  getAnswerEvaluation: vi.fn(),
  confirmAnswerEvaluation: vi.fn(),
  overrideAnswerEvaluation: vi.fn(),
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
  permissions: ["answer_evaluations:read", "answer_evaluations:create"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeEvaluation(overrides: Partial<AnswerEvaluation> = {}): AnswerEvaluation {
  return {
    id: "eval-1",
    institution_id: "inst-1",
    exam_session_id: "session-1",
    answer_script_id: "script-1",
    extracted_question_id: "question-1",
    extracted_model_answer_id: null,
    ai_provider_id: "provider-1",
    student_answer_text: "The mitochondria is the powerhouse of the cell.",
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
    review_status: "pending_confirmation",
    evaluated_at: "2026-01-01T00:00:00Z",
    reviewed_by: null,
    reviewed_at: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: AnswerEvaluation[]): Page<AnswerEvaluation> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
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
            <EvaluationReviewDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("EvaluationReviewDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists answer evaluations for the current institution", async () => {
    listMock.mockResolvedValueOnce(page([makeEvaluation()]));
    renderPage();

    expect(await screen.findByText("session-1")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("8 / 10")).toBeInTheDocument();
    expect(screen.getByText("pending confirmation")).toBeInTheDocument();
  });

  it("shows a loading state before evaluations resolve", () => {
    listMock.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("triggers an evaluation and shows a success toast", async () => {
    listMock.mockResolvedValue(page([]));
    triggerMock.mockResolvedValueOnce(makeEvaluation());
    renderPage();

    await screen.findByText("No answer evaluations found.");
    await userEvent.type(screen.getByLabelText(/^Exam Session ID/), "session-123");
    await userEvent.type(screen.getByLabelText(/^Extracted Question ID/), "question-456");
    await userEvent.click(screen.getByRole("button", { name: "Trigger Evaluation" }));

    await waitFor(() =>
      expect(triggerMock).toHaveBeenCalledWith({
        exam_session_id: "session-123",
        extracted_question_id: "question-456",
      }),
    );
    expect(await screen.findByText("Answer evaluation triggered.")).toBeInTheDocument();
  });

  it("hides the trigger evaluation form when the create permission is absent", async () => {
    listMock.mockResolvedValue(page([]));
    renderPage({ ...baseUser, permissions: ["answer_evaluations:read"] });

    await screen.findByText("No answer evaluations found.");
    expect(screen.queryByText("Trigger Evaluation")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^Exam Session ID/)).not.toBeInTheDocument();
  });

  it("filters the list client-side by confidence tier", async () => {
    listMock.mockResolvedValueOnce(
      page([
        makeEvaluation({ id: "eval-1", exam_session_id: "session-high", confidence_tier: "high" }),
        makeEvaluation({ id: "eval-2", exam_session_id: "session-low", confidence_tier: "low" }),
      ]),
    );
    renderPage();

    await screen.findByText("session-high");
    expect(screen.getByText("session-low")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "High" }));

    expect(screen.getByText("session-high")).toBeInTheDocument();
    expect(screen.queryByText("session-low")).not.toBeInTheDocument();
  });
});
