import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { QuestionVerificationPage } from "@/pages/ocr/QuestionVerificationPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { User } from "@/types/auth";
import type { ExtractedQuestion } from "@/types/officialExam";
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
vi.mock("@/api/extractedQuestions", () => ({
  listExtractedQuestions: listMock,
  getExtractedQuestion: vi.fn(),
  updateExtractedQuestion: updateMock,
  verifyExtractedQuestion: verifyMock,
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

function makeQuestion(overrides: Partial<ExtractedQuestion> = {}): ExtractedQuestion {
  return {
    id: "question-1",
    institution_id: "inst-1",
    document_id: "document-1",
    linked_question_id: null,
    question_number: "1",
    question_text: "Explain photosynthesis.",
    raw_ocr_text: null,
    detected_marks: "10",
    final_marks: null,
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

function page(items: ExtractedQuestion[]): Page<ExtractedQuestion> {
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
        <MemoryRouter initialEntries={[`/dashboard/official-exam-documents/${documentId}/questions`]}>
          <ToastProvider>
            <Routes>
              <Route
                path="/dashboard/official-exam-documents/:documentId/questions"
                element={<QuestionVerificationPage />}
              />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionVerificationPage", () => {
  it("shows a loading state before data resolves", async () => {
    let resolveList: (value: Page<ExtractedQuestion>) => void = () => {};
    listMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );
    renderPage(["extracted_questions:update", "extracted_questions:verify"]);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    resolveList(page([]));
    await screen.findByText("No extracted questions found for this document.");
  });

  it("lists extracted questions filtered by the route's documentId", async () => {
    listMock.mockResolvedValueOnce(page([makeQuestion()]));
    renderPage(["extracted_questions:update", "extracted_questions:verify"]);

    expect(await screen.findByText("Explain photosynthesis.")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ document_id: "document-1" }));
  });

  it("verifies a question and shows a success toast", async () => {
    listMock.mockResolvedValue(page([makeQuestion()]));
    verifyMock.mockResolvedValueOnce(makeQuestion({ verification_status: "verified" }));
    renderPage(["extracted_questions:update", "extracted_questions:verify"]);

    await screen.findByText("Explain photosynthesis.");
    await userEvent.click(screen.getByRole("button", { name: "Verify question 1" }));

    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith("question-1"));
    expect(await screen.findByText("Question verified.")).toBeInTheDocument();
  });

  it("edits a question via the form dialog", async () => {
    listMock.mockResolvedValue(page([makeQuestion()]));
    updateMock.mockResolvedValueOnce(makeQuestion({ question_text: "Explain osmosis.", final_marks: "8" }));
    renderPage(["extracted_questions:update", "extracted_questions:verify"]);

    await screen.findByText("Explain photosynthesis.");
    await userEvent.click(screen.getByRole("button", { name: "Edit question 1" }));

    const textArea = await screen.findByLabelText(/^Question Text/);
    await userEvent.clear(textArea);
    await userEvent.type(textArea, "Explain osmosis.");
    const marksInput = screen.getByLabelText(/^Final Marks/);
    await userEvent.type(marksInput, "8");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("question-1", {
        question_text: "Explain osmosis.",
        final_marks: 8,
      }),
    );
    expect(await screen.findByText("Question updated.")).toBeInTheDocument();
  });

  it("hides the verify button when the permission is absent", async () => {
    listMock.mockResolvedValueOnce(page([makeQuestion()]));
    renderPage(["extracted_questions:update"]);

    await screen.findByText("Explain photosynthesis.");
    expect(screen.queryByRole("button", { name: "Verify question 1" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit question 1" })).toBeInTheDocument();
  });
});
