import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { OfficialDocumentUploadDashboardPage } from "@/pages/ocr/OfficialDocumentUploadDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { OfficialExamDocument } from "@/types/officialExam";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, uploadMock, retryMock, cancelMock, removeMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  uploadMock: vi.fn(),
  retryMock: vi.fn(),
  cancelMock: vi.fn(),
  removeMock: vi.fn(),
}));
vi.mock("@/api/officialExamDocuments", () => ({
  listOfficialExamDocuments: listMock,
  uploadOfficialExamDocument: uploadMock,
  retryOfficialExamDocument: retryMock,
  cancelOfficialExamDocument: cancelMock,
  removeOfficialExamDocument: removeMock,
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

const limitedUser: User = {
  ...baseUser,
  id: "user-2",
  permissions: ["official_exam_documents:read"],
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
    file_size_bytes: 2 * 1024 * 1024,
    checksum_sha256: null,
    storage_key: "key",
    page_count: 4,
    raw_ocr_text: null,
    ocr_status: "completed",
    verification_status: "not_started",
    failure_reason: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: OfficialExamDocument[]): Page<OfficialExamDocument> {
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
            <OfficialDocumentUploadDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("OfficialDocumentUploadDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists official exam documents for the current institution", async () => {
    listMock.mockResolvedValueOnce(page([makeDocument()]));
    renderPage();
    expect(await screen.findByText("question-paper.pdf")).toBeInTheDocument();
    expect(screen.getByText("question paper")).toBeInTheDocument();
  });

  it("uploads a single dropped/selected file once exam id and document type are set", async () => {
    listMock.mockResolvedValue(page([]));
    uploadMock.mockResolvedValueOnce(makeDocument());
    renderPage();

    await screen.findByText("No official exam documents found.");
    await userEvent.type(screen.getByLabelText(/^Exam ID/), "exam-123");
    await userEvent.selectOptions(screen.getByLabelText(/^Document Type/), "question_paper");

    const file = new File(["content"], "single.pdf", { type: "application/pdf" });
    const input = screen.getByLabelText("Upload file") as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith("exam-123", "question_paper", file));
  });

  it("retries a failed document", async () => {
    listMock.mockResolvedValueOnce(page([makeDocument({ ocr_status: "failed" })]));
    retryMock.mockResolvedValueOnce(makeDocument({ ocr_status: "preprocessing" }));
    renderPage();

    await screen.findByText("question-paper.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Retry question-paper.pdf" }));

    await waitFor(() => expect(retryMock).toHaveBeenCalledWith("doc-1"));
  });

  it("cancels an in-progress document", async () => {
    listMock.mockResolvedValueOnce(page([makeDocument({ ocr_status: "ocr_running" })]));
    cancelMock.mockResolvedValueOnce(makeDocument({ ocr_status: "cancelled" }));
    renderPage();

    await screen.findByText("question-paper.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Cancel question-paper.pdf" }));

    await waitFor(() => expect(cancelMock).toHaveBeenCalledWith("doc-1"));
  });

  it("deletes a document after confirmation", async () => {
    listMock.mockResolvedValueOnce(page([makeDocument()]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("question-paper.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Delete question-paper.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("doc-1"));
  });

  it("hides retry/cancel/delete actions when the user lacks the permissions", async () => {
    listMock.mockResolvedValueOnce(page([makeDocument({ ocr_status: "failed" })]));
    renderPage(limitedUser);

    await screen.findByText("question-paper.pdf");
    expect(screen.queryByRole("button", { name: "Retry question-paper.pdf" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel question-paper.pdf" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete question-paper.pdf" })).not.toBeInTheDocument();
  });
});
