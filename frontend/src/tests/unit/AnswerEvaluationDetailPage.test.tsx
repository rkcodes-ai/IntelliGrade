import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AnswerEvaluationDetailPage } from "@/pages/ocr/AnswerEvaluationDetailPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnswerEvaluation, ExtractedModelAnswer } from "@/types/officialExam";
import type { User } from "@/types/auth";

const { getMock, confirmMock, overrideMock, rejectMock, rerunMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  confirmMock: vi.fn(),
  overrideMock: vi.fn(),
  rejectMock: vi.fn(),
  rerunMock: vi.fn(),
}));
vi.mock("@/api/answerEvaluations", () => ({
  getAnswerEvaluation: getMock,
  confirmAnswerEvaluation: confirmMock,
  overrideAnswerEvaluation: overrideMock,
  rejectAnswerEvaluation: rejectMock,
  rerunAnswerEvaluation: rerunMock,
  listAnswerEvaluations: vi.fn(),
  triggerAnswerEvaluation: vi.fn(),
}));

const { getModelAnswerMock } = vi.hoisted(() => ({ getModelAnswerMock: vi.fn() }));
vi.mock("@/api/extractedModelAnswers", () => ({
  getExtractedModelAnswer: getModelAnswerMock,
  listExtractedModelAnswers: vi.fn(),
  updateExtractedModelAnswer: vi.fn(),
  verifyExtractedModelAnswer: vi.fn(),
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
  permissions: ["answer_evaluations:read", "answer_evaluations:confirm", "answer_evaluations:override"],
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
    extracted_model_answer_id: "model-answer-1",
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

function makeModelAnswer(overrides: Partial<ExtractedModelAnswer> = {}): ExtractedModelAnswer {
  return {
    id: "model-answer-1",
    institution_id: "inst-1",
    document_id: "doc-1",
    linked_answer_key_id: null,
    question_number: "3",
    answer_text: "Model answer text.",
    raw_ocr_text: null,
    page_number: 1,
    display_order: 0,
    verification_status: "verified",
    verified_by: "user-1",
    verified_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage(user: User = baseUser, id = "eval-1") {
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
        <MemoryRouter initialEntries={[`/dashboard/answer-evaluations/${id}`]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/answer-evaluations/:id" element={<AnswerEvaluationDetailPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AnswerEvaluationDetailPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders all 7 AI signal scores individually, never collapsed into one number", async () => {
    getMock.mockResolvedValueOnce(makeEvaluation());
    getModelAnswerMock.mockResolvedValueOnce(makeModelAnswer());
    renderPage();

    await screen.findByText("Semantic Similarity");
    expect(screen.getByText("Keyword Match")).toBeInTheDocument();
    expect(screen.getByText("Concept Match")).toBeInTheDocument();
    expect(screen.getByText("Reasoning")).toBeInTheDocument();
    expect(screen.getByText("Completeness")).toBeInTheDocument();
    expect(screen.getByText("Relevance")).toBeInTheDocument();
    expect(screen.getByText("Confidence")).toBeInTheDocument();

    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("88%")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();

    expect(screen.getByText("The mitochondria is the powerhouse of the cell.")).toBeInTheDocument();
    expect(await screen.findByText("3")).toBeInTheDocument();
  });

  it("confirms the evaluation and shows a success toast", async () => {
    getMock.mockResolvedValue(makeEvaluation());
    getModelAnswerMock.mockResolvedValue(makeModelAnswer());
    confirmMock.mockResolvedValueOnce(makeEvaluation({ review_status: "teacher_confirmed" }));
    renderPage();

    await screen.findByText("Semantic Similarity");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(confirmMock).toHaveBeenCalledWith("eval-1"));
    expect(await screen.findByText("Answer evaluation confirmed.")).toBeInTheDocument();
  });

  it("overrides the evaluation with final marks and notes, showing a success toast", async () => {
    getMock.mockResolvedValue(makeEvaluation());
    getModelAnswerMock.mockResolvedValue(makeModelAnswer());
    overrideMock.mockResolvedValueOnce(makeEvaluation({ final_marks: "9", review_status: "teacher_overridden" }));
    renderPage();

    await screen.findByText("Semantic Similarity");
    await userEvent.click(screen.getByRole("button", { name: "Override" }));

    const marksInput = await screen.findByLabelText(/^Final Marks/);
    await userEvent.clear(marksInput);
    await userEvent.type(marksInput, "9");
    await userEvent.type(screen.getByLabelText("Notes (optional)"), "Adjusted for partial credit.");
    await userEvent.click(screen.getByRole("button", { name: "Save Override" }));

    await waitFor(() =>
      expect(overrideMock).toHaveBeenCalledWith("eval-1", {
        final_marks: 9,
        notes: "Adjusted for partial credit.",
      }),
    );
    expect(await screen.findByText("Answer evaluation overridden.")).toBeInTheDocument();
  });

  it("hides Confirm and Override actions when their permissions are absent", async () => {
    getMock.mockResolvedValueOnce(makeEvaluation());
    getModelAnswerMock.mockResolvedValueOnce(makeModelAnswer());
    renderPage({ ...baseUser, permissions: ["answer_evaluations:read"] });

    await screen.findByText("Semantic Similarity");
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Override" })).not.toBeInTheDocument();
  });

  it("does not show Confirm when suggested_marks is null", async () => {
    getMock.mockResolvedValueOnce(makeEvaluation({ suggested_marks: null }));
    getModelAnswerMock.mockResolvedValueOnce(makeModelAnswer());
    renderPage();

    await screen.findByText("Semantic Similarity");
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  });

  it("rejects the evaluation with a reason and shows a success toast", async () => {
    getMock.mockResolvedValue(makeEvaluation());
    getModelAnswerMock.mockResolvedValue(makeModelAnswer());
    rejectMock.mockResolvedValueOnce(
      makeEvaluation({ review_status: "teacher_rejected", final_marks: null }),
    );
    renderPage({
      ...baseUser,
      permissions: [...baseUser.permissions, "answer_evaluations:reject"],
    });

    await screen.findByText("Semantic Similarity");
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));

    const reasonInput = await screen.findByLabelText(/^Reason/);
    await userEvent.type(reasonInput, "AI misread the answer.");
    await userEvent.click(screen.getByRole("button", { name: "Confirm Rejection" }));

    await waitFor(() =>
      expect(rejectMock).toHaveBeenCalledWith("eval-1", { reason: "AI misread the answer." }),
    );
    expect(await screen.findByText("Answer evaluation rejected.")).toBeInTheDocument();
  });

  it("re-runs the AI evaluation and shows a success toast", async () => {
    getMock.mockResolvedValue(makeEvaluation());
    getModelAnswerMock.mockResolvedValue(makeModelAnswer());
    rerunMock.mockResolvedValueOnce(makeEvaluation({ review_status: "pending_confirmation" }));
    renderPage({
      ...baseUser,
      permissions: [...baseUser.permissions, "answer_evaluations:rerun"],
    });

    await screen.findByText("Semantic Similarity");
    await userEvent.click(screen.getByRole("button", { name: "Re-run AI Evaluation" }));

    await waitFor(() => expect(rerunMock).toHaveBeenCalledWith("eval-1"));
    expect(
      await screen.findByText("AI evaluation re-run — a fresh suggestion is now available for review."),
    ).toBeInTheDocument();
  });

  it("hides Reject and Re-run actions when their permissions are absent", async () => {
    getMock.mockResolvedValueOnce(makeEvaluation());
    getModelAnswerMock.mockResolvedValueOnce(makeModelAnswer());
    renderPage({ ...baseUser, permissions: ["answer_evaluations:read"] });

    await screen.findByText("Semantic Similarity");
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Re-run AI Evaluation" })).not.toBeInTheDocument();
  });
});
