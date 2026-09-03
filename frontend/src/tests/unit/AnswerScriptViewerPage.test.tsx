import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AnswerScriptViewerPage } from "@/pages/ocr/AnswerScriptViewerPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnswerScript, AnswerScriptPage } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const {
  getAnswerScriptMock,
  downloadAnswerScriptMock,
  retryAnswerScriptMock,
  cancelAnswerScriptMock,
  removeAnswerScriptMock,
} = vi.hoisted(() => ({
  getAnswerScriptMock: vi.fn(),
  downloadAnswerScriptMock: vi.fn(),
  retryAnswerScriptMock: vi.fn(),
  cancelAnswerScriptMock: vi.fn(),
  removeAnswerScriptMock: vi.fn(),
}));
vi.mock("@/api/answerScripts", () => ({
  getAnswerScript: getAnswerScriptMock,
  downloadAnswerScript: downloadAnswerScriptMock,
  retryAnswerScript: retryAnswerScriptMock,
  cancelAnswerScript: cancelAnswerScriptMock,
  removeAnswerScript: removeAnswerScriptMock,
}));

const { listAnswerScriptPagesMock } = vi.hoisted(() => ({ listAnswerScriptPagesMock: vi.fn() }));
vi.mock("@/api/answerScriptPages", () => ({
  listAnswerScriptPages: listAnswerScriptPagesMock,
  getAnswerScriptPage: vi.fn(),
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

function makeAnswerScript(overrides: Partial<AnswerScript> = {}): AnswerScript {
  return {
    id: "script-1",
    institution_id: "inst-1",
    exam_session_id: "exam-session-1",
    uploaded_by: "user-1",
    original_filename: "answer-sheet.pdf",
    mime_type: "application/pdf",
    page_count: 4,
    file_size_bytes: 2 * 1024 * 1024,
    checksum_sha256: "abcdef1234567890abcdef1234567890",
    storage_key: "scripts/script-1.pdf",
    status: "completed",
    failure_reason: null,
    structured_content: { page_count: 4, pages: [{ detected_questions: ["q1", "q2"] }, { detected_questions: ["q3"] }] },
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const answerScriptPage: AnswerScriptPage = {
  id: "page-1",
  institution_id: "inst-1",
  answer_script_id: "script-1",
  page_number: 1,
  storage_key: "pages/page-1.png",
  preprocessed_storage_key: null,
  quality_score: null,
  quality_classification: null,
  quality_metrics: null,
  enhancement_metadata: null,
  width_px: 1200,
  height_px: 1600,
  is_blank: false,
  status: "ocr_complete",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage(scriptId = "script-1") {
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
        <MemoryRouter initialEntries={[`/dashboard/answer-scripts/${scriptId}`]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/answer-scripts/:id" element={<AnswerScriptViewerPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AnswerScriptViewerPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders answer script detail fields", async () => {
    getAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript());
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([answerScriptPage]));
    renderPage();

    expect(await screen.findByText("answer-sheet.pdf")).toBeInTheDocument();
    expect(screen.getByText("application/pdf")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("2.00 MB")).toBeInTheDocument();
    expect(screen.getByText(/abcdef1234567890/)).toBeInTheDocument();
    expect(screen.getByText(/4 page\(s\) processed, 3 detected question marker\(s\)/)).toBeInTheDocument();
  });

  it("lists the script's pages in the sub-table", async () => {
    getAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript());
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([answerScriptPage]));
    renderPage();

    await screen.findByText("answer-sheet.pdf");
    expect(listAnswerScriptPagesMock).toHaveBeenCalledWith(
      expect.objectContaining({ answer_script_id: "script-1", page_size: 200 }),
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("ocr complete")).toBeInTheDocument();
    expect(screen.getByText("1200x1600")).toBeInTheDocument();
  });

  it("navigates to the page viewer when View Page is clicked", async () => {
    getAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript());
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([answerScriptPage]));
    renderPage();

    await screen.findByText("answer-sheet.pdf");
    await userEvent.click(screen.getByRole("button", { name: "View Page 1" }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/answer-scripts/script-1/pages/page-1");
  });

  it("downloads the answer script and opens the presigned url", async () => {
    getAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript());
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([]));
    downloadAnswerScriptMock.mockResolvedValueOnce({ url: "https://storage.example.com/file.pdf" });
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderPage();

    await screen.findByText("answer-sheet.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Download" }));

    await waitFor(() => expect(downloadAnswerScriptMock).toHaveBeenCalledWith("script-1"));
    await waitFor(() =>
      expect(openSpy).toHaveBeenCalledWith("https://storage.example.com/file.pdf", "_blank"),
    );
  });

  it("retries a failed answer script", async () => {
    getAnswerScriptMock.mockResolvedValue(makeAnswerScript({ status: "failed", failure_reason: "OCR error" }));
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([]));
    retryAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript({ status: "ocr_queued" }));
    renderPage();

    await screen.findByText("answer-sheet.pdf");
    expect(screen.getByText("OCR error")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(retryAnswerScriptMock).toHaveBeenCalledWith("script-1"));
  });

  it("cancels an in-progress answer script", async () => {
    getAnswerScriptMock.mockResolvedValue(makeAnswerScript({ status: "ocr_running" }));
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([]));
    cancelAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript({ status: "cancelled" }));
    renderPage();

    await screen.findByText("answer-sheet.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(cancelAnswerScriptMock).toHaveBeenCalledWith("script-1"));
  });

  it("deletes the answer script after confirmation and navigates back to the list", async () => {
    getAnswerScriptMock.mockResolvedValueOnce(makeAnswerScript());
    listAnswerScriptPagesMock.mockResolvedValueOnce(page([]));
    removeAnswerScriptMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("answer-sheet.pdf");
    await userEvent.click(screen.getByRole("button", { name: "Delete answer-sheet.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(removeAnswerScriptMock).toHaveBeenCalledWith("script-1"));
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/dashboard/answer-scripts"));
  });
});
