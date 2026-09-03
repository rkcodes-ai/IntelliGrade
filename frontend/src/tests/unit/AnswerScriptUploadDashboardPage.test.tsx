import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AnswerScriptUploadDashboardPage } from "@/pages/ocr/AnswerScriptUploadDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnswerScript } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, uploadMock, bulkUploadMock, retryMock, cancelMock, removeMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  uploadMock: vi.fn(),
  bulkUploadMock: vi.fn(),
  retryMock: vi.fn(),
  cancelMock: vi.fn(),
  removeMock: vi.fn(),
}));
vi.mock("@/api/answerScripts", () => ({
  listAnswerScripts: listMock,
  uploadAnswerScript: uploadMock,
  bulkUploadAnswerScripts: bulkUploadMock,
  retryAnswerScript: retryMock,
  cancelAnswerScript: cancelMock,
  removeAnswerScript: removeMock,
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
    "answer_scripts:read",
    "answer_scripts:retry",
    "answer_scripts:cancel",
    "answer_scripts:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeScript(overrides: Partial<AnswerScript> = {}): AnswerScript {
  return {
    id: "script-1",
    institution_id: "inst-1",
    exam_session_id: "session-1",
    uploaded_by: "user-1",
    original_filename: "answer-script.pdf",
    mime_type: "application/pdf",
    page_count: 4,
    file_size_bytes: 2 * 1024 * 1024,
    checksum_sha256: null,
    storage_key: "key",
    status: "completed",
    failure_reason: null,
    structured_content: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: AnswerScript[]): Page<AnswerScript> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage() {
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
        <MemoryRouter>
          <ToastProvider>
            <AnswerScriptUploadDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AnswerScriptUploadDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists answer scripts for the current institution", async () => {
    listMock.mockResolvedValueOnce(page([makeScript()]));
    renderPage();
    expect(await screen.findByText("answer-script.pdf")).toBeInTheDocument();
    expect(screen.getByText("2.00 MB")).toBeInTheDocument();
  });

  it("uploads a single dropped/selected file", async () => {
    listMock.mockResolvedValue(page([]));
    uploadMock.mockResolvedValueOnce(makeScript());
    renderPage();

    await screen.findByText("No answer scripts found.");
    await userEvent.type(screen.getByLabelText(/^Exam Session ID/), "session-123");

    const file = new File(["content"], "single.pdf", { type: "application/pdf" });
    const input = screen.getByLabelText("Upload files") as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith("session-123", file));
    expect(bulkUploadMock).not.toHaveBeenCalled();
  });

  it("bulk uploads multiple files dropped onto the drop zone", async () => {
    listMock.mockResolvedValue(page([]));
    bulkUploadMock.mockResolvedValueOnce({ created: 2, errors: [] });
    renderPage();

    await screen.findByText("No answer scripts found.");
    await userEvent.type(screen.getByLabelText(/^Exam Session ID/), "session-456");

    const file1 = new File(["a"], "one.pdf", { type: "application/pdf" });
    const file2 = new File(["b"], "two.pdf", { type: "application/pdf" });
    const dropzone = screen.getByRole("button", { name: /drag & drop files here/i });

    fireEvent.drop(dropzone, { dataTransfer: { files: [file1, file2] } });

    await waitFor(() => expect(bulkUploadMock).toHaveBeenCalledWith("session-456", [file1, file2]));
    expect(uploadMock).not.toHaveBeenCalled();
  });

  it("retries a failed answer script", async () => {
    listMock.mockResolvedValueOnce(page([makeScript({ status: "failed" })]));
    retryMock.mockResolvedValueOnce(makeScript({ status: "ocr_queued" }));
    renderPage();

    await screen.findByText("answer-script.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Retry answer-script.pdf" }));

    await waitFor(() => expect(retryMock).toHaveBeenCalledWith("script-1"));
  });

  it("cancels an in-progress answer script", async () => {
    listMock.mockResolvedValueOnce(page([makeScript({ status: "ocr_running" })]));
    cancelMock.mockResolvedValueOnce(makeScript({ status: "cancelled" }));
    renderPage();

    await screen.findByText("answer-script.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Cancel answer-script.pdf" }));

    await waitFor(() => expect(cancelMock).toHaveBeenCalledWith("script-1"));
  });

  it("deletes an answer script after confirmation", async () => {
    listMock.mockResolvedValueOnce(page([makeScript()]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("answer-script.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Delete answer-script.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("script-1"));
  });
});
