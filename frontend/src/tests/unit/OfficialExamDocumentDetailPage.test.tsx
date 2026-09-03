import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { OfficialExamDocumentDetailPage } from "@/pages/ocr/OfficialExamDocumentDetailPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { User } from "@/types/auth";
import type { OfficialExamDocument } from "@/types/officialExam";

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const {
  getOfficialExamDocumentMock,
  downloadOfficialExamDocumentMock,
  retryOfficialExamDocumentMock,
  cancelOfficialExamDocumentMock,
  removeOfficialExamDocumentMock,
} = vi.hoisted(() => ({
  getOfficialExamDocumentMock: vi.fn(),
  downloadOfficialExamDocumentMock: vi.fn(),
  retryOfficialExamDocumentMock: vi.fn(),
  cancelOfficialExamDocumentMock: vi.fn(),
  removeOfficialExamDocumentMock: vi.fn(),
}));
vi.mock("@/api/officialExamDocuments", () => ({
  getOfficialExamDocument: getOfficialExamDocumentMock,
  downloadOfficialExamDocument: downloadOfficialExamDocumentMock,
  retryOfficialExamDocument: retryOfficialExamDocumentMock,
  cancelOfficialExamDocument: cancelOfficialExamDocumentMock,
  removeOfficialExamDocument: removeOfficialExamDocumentMock,
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
    "official_exam_documents:read",
    "official_exam_documents:retry",
    "official_exam_documents:cancel",
    "official_exam_documents:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeDocument(overrides: Partial<OfficialExamDocument> = {}): OfficialExamDocument {
  return {
    id: "doc-1",
    institution_id: "inst-1",
    exam_id: "exam-1",
    uploaded_by: "user-1",
    document_type: "question_paper",
    original_filename: "question-paper.pdf",
    mime_type: "application/pdf",
    file_size_bytes: 1024 * 1024,
    checksum_sha256: "abcdef1234567890abcdef1234567890",
    storage_key: "docs/doc-1.pdf",
    page_count: 3,
    raw_ocr_text: "Q1) ...",
    ocr_status: "completed",
    verification_status: "not_started",
    failure_reason: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage(documentId = "doc-1") {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: baseUser, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/dashboard/official-exam-documents/${documentId}`]}>
          <ToastProvider>
            <Routes>
              <Route
                path="/dashboard/official-exam-documents/:id"
                element={<OfficialExamDocumentDetailPage />}
              />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("OfficialExamDocumentDetailPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders document detail fields", async () => {
    getOfficialExamDocumentMock.mockResolvedValueOnce(makeDocument());
    renderPage();

    expect(await screen.findByText("question-paper.pdf")).toBeInTheDocument();
    expect(screen.getByText("application/pdf")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("question paper")).toBeInTheDocument();
    expect(screen.getByText("1.00 MB")).toBeInTheDocument();
  });

  it("navigates to the question verification screen for a completed question paper", async () => {
    getOfficialExamDocumentMock.mockResolvedValueOnce(makeDocument());
    renderPage();

    await screen.findByText("question-paper.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Verify Extracted Questions" }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/official-exam-documents/doc-1/questions");
  });

  it("navigates to the mark scheme verification screen for a completed mark scheme document", async () => {
    getOfficialExamDocumentMock.mockResolvedValueOnce(
      makeDocument({ document_type: "mark_scheme" }),
    );
    renderPage();

    await screen.findByText("question-paper.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Verify Mark Scheme Ranges" }));
    expect(navigateMock).toHaveBeenCalledWith(
      "/dashboard/official-exam-documents/doc-1/mark-scheme",
    );
  });

  it("does not show the verify action while ingestion is still running", async () => {
    getOfficialExamDocumentMock.mockResolvedValueOnce(
      makeDocument({ ocr_status: "ocr_running" }),
    );
    renderPage();

    await screen.findByText("question-paper.pdf");
    expect(screen.queryByRole("button", { name: /Verify Extracted/ })).not.toBeInTheDocument();
  });

  it("retries a failed document", async () => {
    getOfficialExamDocumentMock.mockResolvedValueOnce(
      makeDocument({ ocr_status: "failed", failure_reason: "OCR timed out" }),
    );
    retryOfficialExamDocumentMock.mockResolvedValueOnce(makeDocument({ ocr_status: "stored" }));
    renderPage();

    await screen.findByText("question-paper.pdf");
    expect(screen.getByText("OCR timed out")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retryOfficialExamDocumentMock).toHaveBeenCalledWith("doc-1");
  });

  it("hides the delete action when the user lacks the delete permission", async () => {
    const store = configureStore({
      reducer: { auth: authReducer, institution: institutionReducer },
      preloadedState: {
        auth: {
          user: { ...baseUser, permissions: ["official_exam_documents:read"] },
          accessToken: "token",
          status: "authenticated" as const,
        },
        institution: { currentInstitutionId: "inst-1" },
      },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    getOfficialExamDocumentMock.mockResolvedValueOnce(makeDocument());

    render(
      <QueryClientProvider client={queryClient}>
        <Provider store={store}>
          <MemoryRouter initialEntries={["/dashboard/official-exam-documents/doc-1"]}>
            <ToastProvider>
              <Routes>
                <Route
                  path="/dashboard/official-exam-documents/:id"
                  element={<OfficialExamDocumentDetailPage />}
                />
              </Routes>
            </ToastProvider>
          </MemoryRouter>
        </Provider>
      </QueryClientProvider>,
    );

    await screen.findByText("question-paper.pdf");
    expect(screen.queryByRole("button", { name: /Delete/ })).not.toBeInTheDocument();
  });
});
