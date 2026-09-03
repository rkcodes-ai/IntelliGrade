import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { PageViewerPage } from "@/pages/ocr/PageViewerPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AnswerScriptPage, OCRResult } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { getAnswerScriptPageMock } = vi.hoisted(() => ({ getAnswerScriptPageMock: vi.fn() }));
vi.mock("@/api/answerScriptPages", () => ({
  listAnswerScriptPages: vi.fn(),
  getAnswerScriptPage: getAnswerScriptPageMock,
}));

const { listOCRResultsMock } = vi.hoisted(() => ({ listOCRResultsMock: vi.fn() }));
vi.mock("@/api/ocrResults", () => ({
  listOCRResults: listOCRResultsMock,
  getOCRResult: vi.fn(),
  getOCRResultBlocks: vi.fn(),
  listOCRBlocks: vi.fn(),
  listOCRLines: vi.fn(),
  listOCRWords: vi.fn(),
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
  permissions: [],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const answerScriptPage: AnswerScriptPage = {
  id: "page-1",
  institution_id: "inst-1",
  answer_script_id: "script-1",
  page_number: 3,
  storage_key: "pages/page-1-original.png",
  preprocessed_storage_key: "pages/page-1-preprocessed.png",
  quality_score: "81.47",
  quality_classification: "GOOD",
  quality_metrics: null,
  enhancement_metadata: null,
  width_px: 1200,
  height_px: 1600,
  is_blank: false,
  status: "ocr_complete",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function makeOCRResult(overrides: Partial<OCRResult> = {}): OCRResult {
  return {
    id: "result-1",
    institution_id: "inst-1",
    answer_script_page_id: "page-1",
    ocr_job_id: "job-1",
    raw_text: "raw",
    normalized_text: null,
    average_confidence: "0.95",
    language: "eng",
    rotation_degrees: "0",
    reading_order_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
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
        <MemoryRouter initialEntries={["/dashboard/answer-scripts/script-1/pages/page-1"]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/answer-scripts/:scriptId/pages/:pageId" element={<PageViewerPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("PageViewerPage", () => {
  it("renders page detail fields and the metadata-only placeholder", async () => {
    getAnswerScriptPageMock.mockResolvedValueOnce(answerScriptPage);
    listOCRResultsMock.mockResolvedValueOnce(page([]));
    renderPage();

    expect(await screen.findByText("Page 3", { selector: "h1" })).toBeInTheDocument();
    expect(screen.getByText("ocr complete")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
    expect(screen.getByText("1200x1600")).toBeInTheDocument();
    expect(screen.getByText("GOOD (81.47)")).toBeInTheDocument();
    expect(screen.getByText("pages/page-1-original.png")).toBeInTheDocument();
    expect(screen.getByText("pages/page-1-preprocessed.png")).toBeInTheDocument();
    expect(screen.getByText(/Image preview requires a presigned per-page URL endpoint/)).toBeInTheDocument();
  });

  it("does not show View OCR Text when no OCRResult matches this page", async () => {
    getAnswerScriptPageMock.mockResolvedValueOnce(answerScriptPage);
    listOCRResultsMock.mockResolvedValueOnce(page([makeOCRResult({ answer_script_page_id: "some-other-page" })]));
    renderPage();

    await screen.findByText("Page 3", { selector: "h1" });
    expect(screen.queryByRole("button", { name: "View OCR Text" })).not.toBeInTheDocument();
  });

  it("navigates to the OCR Text Viewer when View OCR Text is clicked", async () => {
    getAnswerScriptPageMock.mockResolvedValueOnce(answerScriptPage);
    listOCRResultsMock.mockResolvedValueOnce(page([makeOCRResult({ id: "result-42", answer_script_page_id: "page-1" })]));
    renderPage();

    await screen.findByText("Page 3", { selector: "h1" });
    await userEvent.click(screen.getByRole("button", { name: "View OCR Text" }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/ocr-results/result-42");
  });

  it("navigates back when Back to script is clicked", async () => {
    getAnswerScriptPageMock.mockResolvedValueOnce(answerScriptPage);
    listOCRResultsMock.mockResolvedValueOnce(page([]));
    renderPage();

    await screen.findByText("Page 3", { selector: "h1" });
    await userEvent.click(screen.getByRole("button", { name: "Back to script" }));
    expect(navigateMock).toHaveBeenCalledWith(-1);
  });
});
