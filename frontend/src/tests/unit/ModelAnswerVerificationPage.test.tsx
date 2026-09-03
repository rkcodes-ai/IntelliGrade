import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { ModelAnswerVerificationPage } from "@/pages/ocr/ModelAnswerVerificationPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { User } from "@/types/auth";
import type { ExtractedModelAnswer } from "@/types/officialExam";
import type { Page } from "@/types/pagination";

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { listMock, updateMock, verifyMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  updateMock: vi.fn(),
  verifyMock: vi.fn(),
}));
vi.mock("@/api/extractedModelAnswers", () => ({
  listExtractedModelAnswers: listMock,
  getExtractedModelAnswer: vi.fn(),
  updateExtractedModelAnswer: updateMock,
  verifyExtractedModelAnswer: verifyMock,
}));

function makeUser(permissions: string[]): User {
  return {
    id: "user-1",
    email: "teacher@example.com",
    username: "teacher",
    full_name: "Teacher",
    phone: null,
    avatar_url: null,
    timezone: "UTC",
    language: "en",
    preferences: {},
    is_active: true,
    is_verified: true,
    roles: ["teacher"],
    permissions,
    last_login_at: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

function makeAnswer(overrides: Partial<ExtractedModelAnswer> = {}): ExtractedModelAnswer {
  return {
    id: "answer-1",
    institution_id: "inst-1",
    document_id: "document-1",
    linked_answer_key_id: null,
    question_number: "1",
    answer_text: "Photosynthesis converts light energy into chemical energy.",
    raw_ocr_text: null,
    page_number: 1,
    display_order: 0,
    verification_status: "pending",
    verified_by: null,
    verified_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: ExtractedModelAnswer[]): Page<ExtractedModelAnswer> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage(permissions: string[], documentId = "document-1") {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: makeUser(permissions), accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/dashboard/official-exam-documents/${documentId}/model-answers`]}>
          <ToastProvider>
            <Routes>
              <Route
                path="/dashboard/official-exam-documents/:documentId/model-answers"
                element={<ModelAnswerVerificationPage />}
              />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ModelAnswerVerificationPage", () => {
  it("shows a loading state before data resolves", async () => {
    let resolveList: (value: Page<ExtractedModelAnswer>) => void = () => {};
    listMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );
    renderPage(["extracted_model_answers:update", "extracted_model_answers:verify"]);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    resolveList(page([]));
    await screen.findByText("No extracted model answers found for this document.");
  });

  it("lists extracted model answers filtered by the route's documentId", async () => {
    listMock.mockResolvedValueOnce(page([makeAnswer()]));
    renderPage(["extracted_model_answers:update", "extracted_model_answers:verify"]);

    expect(
      await screen.findByText("Photosynthesis converts light energy into chemical energy."),
    ).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ document_id: "document-1" }));
  });

  it("verifies a model answer and shows a success toast", async () => {
    listMock.mockResolvedValue(page([makeAnswer()]));
    verifyMock.mockResolvedValueOnce(makeAnswer({ verification_status: "verified" }));
    renderPage(["extracted_model_answers:update", "extracted_model_answers:verify"]);

    await screen.findByText("Photosynthesis converts light energy into chemical energy.");
    await userEvent.click(screen.getByRole("button", { name: "Verify model answer 1" }));

    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith("answer-1"));
    expect(await screen.findByText("Model answer verified.")).toBeInTheDocument();
  });

  it("edits a model answer via the form dialog", async () => {
    listMock.mockResolvedValue(page([makeAnswer()]));
    updateMock.mockResolvedValueOnce(makeAnswer({ answer_text: "Updated answer text." }));
    renderPage(["extracted_model_answers:update", "extracted_model_answers:verify"]);

    await screen.findByText("Photosynthesis converts light energy into chemical energy.");
    await userEvent.click(screen.getByRole("button", { name: "Edit model answer 1" }));

    const textArea = await screen.findByLabelText(/^Answer Text/);
    await userEvent.clear(textArea);
    await userEvent.type(textArea, "Updated answer text.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("answer-1", { answer_text: "Updated answer text." }),
    );
    expect(await screen.findByText("Model answer updated.")).toBeInTheDocument();
  });

  it("hides the verify button when the permission is absent", async () => {
    listMock.mockResolvedValueOnce(page([makeAnswer()]));
    renderPage(["extracted_model_answers:update"]);

    await screen.findByText("Photosynthesis converts light energy into chemical energy.");
    expect(screen.queryByRole("button", { name: "Verify model answer 1" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit model answer 1" })).toBeInTheDocument();
  });
});
