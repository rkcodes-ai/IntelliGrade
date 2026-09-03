import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AIReferenceAnswerDashboardPage } from "@/pages/ocr/AIReferenceAnswerDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AIReferenceAnswer } from "@/types/aiReferenceAnswer";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }));
vi.mock("@/api/aiReferenceAnswers", () => ({
  listAIReferenceAnswers: listMock,
  getAIReferenceAnswer: vi.fn(),
  getCurrentAIReferenceAnswerForQuestion: vi.fn(),
  listAIReferenceAnswerVersions: vi.fn(),
  generateAIReferenceAnswer: vi.fn(),
  approveAIReferenceAnswer: vi.fn(),
  rejectAIReferenceAnswer: vi.fn(),
  regenerateAIReferenceAnswer: vi.fn(),
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
  permissions: ["ai_reference_answers:read"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

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
    question_text: "Explain photosynthesis.",
    official_model_answer_text: "Photosynthesis converts light energy into chemical energy.",
    synthesized_reference_answer: "Photosynthesis converts light energy into chemical energy.",
    structured_content: null,
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

function page(items: AIReferenceAnswer[]): Page<AIReferenceAnswer> {
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
          <AIReferenceAnswerDashboardPage />
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AIReferenceAnswerDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists AI reference answers for the current institution", async () => {
    listMock.mockResolvedValueOnce(page([makeReference()]));
    renderPage();

    expect(await screen.findByText("question-1")).toBeInTheDocument();
    expect(screen.getByText("pending verification")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("45.00%")).toBeInTheDocument();
  });

  it("shows a loading state before the list resolves", () => {
    listMock.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows an empty state when there are no AI reference answers", async () => {
    listMock.mockResolvedValueOnce(page([]));
    renderPage();

    expect(await screen.findByText("No AI reference answers found.")).toBeInTheDocument();
  });
});
