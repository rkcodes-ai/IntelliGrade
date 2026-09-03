import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AIReferenceAnswerReviewPage } from "@/pages/ocr/AIReferenceAnswerReviewPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AIReferenceAnswer } from "@/types/aiReferenceAnswer";
import type { ExtractedQuestion } from "@/types/officialExam";
import type { User } from "@/types/auth";

const {
  getCurrentMock,
  listVersionsMock,
  generateMock,
  approveMock,
  rejectMock,
  regenerateMock,
} = vi.hoisted(() => ({
  getCurrentMock: vi.fn(),
  listVersionsMock: vi.fn(),
  generateMock: vi.fn(),
  approveMock: vi.fn(),
  rejectMock: vi.fn(),
  regenerateMock: vi.fn(),
}));
vi.mock("@/api/aiReferenceAnswers", () => ({
  getCurrentAIReferenceAnswerForQuestion: getCurrentMock,
  listAIReferenceAnswerVersions: listVersionsMock,
  generateAIReferenceAnswer: generateMock,
  approveAIReferenceAnswer: approveMock,
  rejectAIReferenceAnswer: rejectMock,
  regenerateAIReferenceAnswer: regenerateMock,
  listAIReferenceAnswers: vi.fn(),
  getAIReferenceAnswer: vi.fn(),
}));

const { getQuestionMock } = vi.hoisted(() => ({ getQuestionMock: vi.fn() }));
vi.mock("@/api/extractedQuestions", () => ({
  getExtractedQuestion: getQuestionMock,
  listExtractedQuestions: vi.fn(),
  updateExtractedQuestion: vi.fn(),
  verifyExtractedQuestion: vi.fn(),
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
  permissions: [
    "ai_reference_answers:read",
    "ai_reference_answers:create",
    "ai_reference_answers:approve",
    "ai_reference_answers:reject",
    "ai_reference_answers:regenerate",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeQuestion(overrides: Partial<ExtractedQuestion> = {}): ExtractedQuestion {
  return {
    id: "question-1",
    institution_id: "inst-1",
    document_id: "doc-1",
    linked_question_id: null,
    question_number: "3",
    question_text: "Explain the process of photosynthesis.",
    raw_ocr_text: null,
    detected_marks: "10",
    final_marks: "10",
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

function makeReference(overrides: Partial<AIReferenceAnswer> = {}): AIReferenceAnswer {
  return {
    id: "ref-1",
    institution_id: "inst-1",
    extracted_question_id: "question-1",
    extracted_model_answer_id: "model-answer-1",
    rubric_id: null,
    ai_provider_id: "provider-1",
    version: 1,
    is_current: true,
    status: "pending_verification",
    question_text: "Explain the process of photosynthesis.",
    official_model_answer_text: "Photosynthesis converts light energy into chemical energy.",
    synthesized_reference_answer:
      "Photosynthesis converts light energy into chemical energy, using chlorophyll in chloroplasts.",
    structured_content: {
      required_concepts: ["chlorophyll", "light energy"],
      optional_concepts: [],
      keywords: ["photosynthesis"],
      equivalent_terms: [],
      alternative_valid_answers: [],
      expected_reasoning: [],
      common_misconceptions: [],
      scoring_guidance: ["Award 2 marks for mentioning chlorophyll."],
    },
    maximum_marks: "10.00",
    marks_source: "final_marks",
    provider_model: "lexical_heuristic",
    prompt_version: null,
    generation_confidence: "45.00",
    generation_error: null,
    has_conflict_flag: false,
    conflict_notes: null,
    rejection_reason: null,
    generated_at: "2026-01-01T00:00:00Z",
    verified_by: null,
    verified_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage(user: User = baseUser, questionId = "question-1") {
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
        <MemoryRouter
          initialEntries={[`/dashboard/extracted-questions/${questionId}/ai-reference-answer`]}
        >
          <ToastProvider>
            <Routes>
              <Route
                path="/dashboard/extracted-questions/:extractedQuestionId/ai-reference-answer"
                element={<AIReferenceAnswerReviewPage />}
              />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AIReferenceAnswerReviewPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the question, official model answer, and structured AI reference content side by side", async () => {
    getQuestionMock.mockResolvedValueOnce(makeQuestion());
    getCurrentMock.mockResolvedValueOnce(makeReference());
    listVersionsMock.mockResolvedValueOnce([makeReference()]);
    renderPage();

    expect(await screen.findByText("Explain the process of photosynthesis.")).toBeInTheDocument();
    expect(
      screen.getByText("Photosynthesis converts light energy into chemical energy."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Photosynthesis converts light energy into chemical energy, using chlorophyll in chloroplasts.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("chlorophyll")).toBeInTheDocument();
    expect(screen.getByText("Award 2 marks for mentioning chlorophyll.")).toBeInTheDocument();
    expect(screen.getAllByText("pending verification").length).toBeGreaterThan(0);
  });

  it("shows a Generate button and empty state when no reference has been generated yet", async () => {
    getQuestionMock.mockResolvedValueOnce(makeQuestion());
    getCurrentMock.mockResolvedValueOnce(null);
    listVersionsMock.mockResolvedValueOnce([]);
    renderPage();

    await screen.findByText("Explain the process of photosynthesis.");
    expect(
      screen.getByText("No AI reference answer has been generated for this question yet."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Reference" })).toBeInTheDocument();
  });

  it("generates a reference and shows a success toast", async () => {
    getQuestionMock.mockResolvedValue(makeQuestion());
    getCurrentMock.mockResolvedValue(null);
    listVersionsMock.mockResolvedValue([]);
    generateMock.mockResolvedValueOnce(makeReference());
    renderPage();

    await screen.findByText("No AI reference answer has been generated for this question yet.");
    await userEvent.click(screen.getByRole("button", { name: "Generate Reference" }));

    await waitFor(() =>
      expect(generateMock).toHaveBeenCalledWith({ extracted_question_id: "question-1" }),
    );
    expect(
      await screen.findByText("AI reference answer generated — pending teacher verification."),
    ).toBeInTheDocument();
  });

  it("approves a pending reference and shows a success toast", async () => {
    getQuestionMock.mockResolvedValue(makeQuestion());
    getCurrentMock.mockResolvedValue(makeReference());
    listVersionsMock.mockResolvedValue([makeReference()]);
    approveMock.mockResolvedValueOnce(makeReference({ status: "approved" }));
    renderPage();

    await screen.findAllByText("pending verification");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(approveMock).toHaveBeenCalledWith("ref-1"));
    expect(await screen.findByText("AI reference answer approved for evaluation.")).toBeInTheDocument();
  });

  it("rejects a pending reference with a reason and shows a success toast", async () => {
    getQuestionMock.mockResolvedValue(makeQuestion());
    getCurrentMock.mockResolvedValue(makeReference());
    listVersionsMock.mockResolvedValue([makeReference()]);
    rejectMock.mockResolvedValueOnce(makeReference({ status: "rejected" }));
    renderPage();

    await screen.findAllByText("pending verification");
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));

    const reasonInput = await screen.findByLabelText(/^Reason/);
    await userEvent.type(reasonInput, "Misses a key concept.");
    await userEvent.click(screen.getByRole("button", { name: "Confirm Rejection" }));

    await waitFor(() =>
      expect(rejectMock).toHaveBeenCalledWith("ref-1", { reason: "Misses a key concept." }),
    );
    expect(await screen.findByText("AI reference answer rejected.")).toBeInTheDocument();
  });

  it("regenerates a reference and shows a success toast", async () => {
    getQuestionMock.mockResolvedValue(makeQuestion());
    getCurrentMock.mockResolvedValue(makeReference({ status: "approved" }));
    listVersionsMock.mockResolvedValue([makeReference({ status: "approved" })]);
    regenerateMock.mockResolvedValueOnce(makeReference({ version: 2 }));
    renderPage();

    await screen.findAllByText("approved");
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));

    await waitFor(() => expect(regenerateMock).toHaveBeenCalledWith("question-1"));
    expect(
      await screen.findByText("A new AI reference answer version was generated."),
    ).toBeInTheDocument();
  });

  it("hides Approve, Reject, and Regenerate actions when their permissions are absent", async () => {
    getQuestionMock.mockResolvedValueOnce(makeQuestion());
    getCurrentMock.mockResolvedValueOnce(makeReference());
    listVersionsMock.mockResolvedValueOnce([makeReference()]);
    renderPage({ ...baseUser, permissions: ["ai_reference_answers:read"] });

    await screen.findAllByText("pending verification");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Regenerate" })).not.toBeInTheDocument();
  });

  it("shows a conflict warning when the AI flags a conflict with the official answer", async () => {
    getQuestionMock.mockResolvedValueOnce(makeQuestion());
    getCurrentMock.mockResolvedValueOnce(
      makeReference({ has_conflict_flag: true, conflict_notes: "Disagrees on the primary pigment." }),
    );
    listVersionsMock.mockResolvedValueOnce([makeReference()]);
    renderPage();

    expect(await screen.findByText("Conflict With Official Answer")).toBeInTheDocument();
    expect(screen.getByText("Disagrees on the primary pigment.")).toBeInTheDocument();
  });
});
