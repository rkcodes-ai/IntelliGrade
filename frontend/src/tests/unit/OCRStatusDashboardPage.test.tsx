import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { OCRStatusDashboardPage } from "@/pages/ocr/OCRStatusDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { OCRJob, OCRProvider } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { listOCRJobsMock, cancelOCRJobMock, listOCRProvidersMock } = vi.hoisted(() => ({
  listOCRJobsMock: vi.fn(),
  cancelOCRJobMock: vi.fn(),
  listOCRProvidersMock: vi.fn(),
}));
vi.mock("@/api/ocrJobs", () => ({
  listOCRJobs: listOCRJobsMock,
  getOCRJob: vi.fn(),
  createOCRJob: vi.fn(),
  cancelOCRJob: cancelOCRJobMock,
}));
vi.mock("@/api/ocrProviders", () => ({
  listOCRProviders: listOCRProvidersMock,
  getOCRProvider: vi.fn(),
  updateOCRProvider: vi.fn(),
}));

function buildUser(permissions: string[]): User {
  return {
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
    permissions,
    last_login_at: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const queuedJob: OCRJob = {
  id: "job-queued-1",
  institution_id: "inst-1",
  answer_script_id: "script-11111111",
  ocr_provider_id: "provider-1",
  requested_ocr_provider_id: null,
  fallback_reason: null,
  celery_task_id: null,
  status: "queued",
  priority: 5,
  retry_count: 0,
  max_retries: 3,
  started_at: null,
  completed_at: null,
  error_message: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const completedJob: OCRJob = {
  ...queuedJob,
  id: "job-completed-1",
  answer_script_id: "script-22222222",
  ocr_provider_id: "provider-2",
  status: "completed",
  retry_count: 1,
  started_at: "2026-01-01T00:01:00Z",
  completed_at: "2026-01-01T00:02:00Z",
};

const providers: OCRProvider[] = [
  {
    id: "provider-1",
    code: "tesseract",
    name: "Tesseract OCR",
    description: null,
    is_enabled: true,
    is_implemented: true,
    is_default: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "provider-2",
    code: "textract",
    name: "AWS Textract",
    description: null,
    is_enabled: true,
    is_implemented: true,
    is_default: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function jobPage(items: OCRJob[]): Page<OCRJob> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function providerPage(items: OCRProvider[]): Page<OCRProvider> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
}

function renderPage(permissions: string[]) {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: buildUser(permissions), accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter>
          <ToastProvider>
            <OCRStatusDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("OCRStatusDashboardPage", () => {
  it("lists OCR jobs with status badges and resolved provider names", async () => {
    listOCRJobsMock.mockResolvedValue(jobPage([queuedJob, completedJob]));
    listOCRProvidersMock.mockResolvedValue(providerPage(providers));
    renderPage(["ocr_jobs:cancel"]);

    expect(await screen.findByText("Tesseract OCR")).toBeInTheDocument();
    expect(await screen.findByText("AWS Textract")).toBeInTheDocument();
    // "queued"/"completed" now also appear as summary-tile titles and filter
    // buttons, not just the row badge, so assert on the table row directly.
    const jobRow = screen.getByText(`${queuedJob.answer_script_id.slice(0, 8)}…`).closest("tr");
    expect(jobRow).not.toBeNull();
    expect(within(jobRow as HTMLElement).getByText("queued")).toBeInTheDocument();
    expect(screen.getByText("0/3")).toBeInTheDocument();

    // Summary tiles (computed from the recent-sample query, same mock data).
    expect(screen.getByRole("heading", { name: "Queued" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Completed" })).toBeInTheDocument();
  });

  it("filters the visible rows by status via the filter buttons", async () => {
    listOCRJobsMock.mockResolvedValue(jobPage([queuedJob, completedJob]));
    listOCRProvidersMock.mockResolvedValue(providerPage(providers));
    renderPage(["ocr_jobs:cancel"]);

    await screen.findByText("Tesseract OCR");
    expect(screen.getByText(`${queuedJob.answer_script_id.slice(0, 8)}…`)).toBeInTheDocument();
    expect(screen.getByText(`${completedJob.answer_script_id.slice(0, 8)}…`)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Completed" }));

    expect(screen.queryByText(`${queuedJob.answer_script_id.slice(0, 8)}…`)).not.toBeInTheDocument();
    expect(screen.getByText(`${completedJob.answer_script_id.slice(0, 8)}…`)).toBeInTheDocument();
  });

  it("calls cancelOCRJob only for a cancellable row when permitted", async () => {
    listOCRJobsMock.mockResolvedValue(jobPage([queuedJob, completedJob]));
    listOCRProvidersMock.mockResolvedValue(providerPage(providers));
    cancelOCRJobMock.mockResolvedValueOnce({ ...queuedJob, status: "cancelled" });
    renderPage(["ocr_jobs:cancel"]);

    await screen.findByText("Tesseract OCR");
    expect(screen.getByRole("button", { name: `Cancel OCR job ${queuedJob.id.slice(0, 8)}…` })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: `Cancel OCR job ${completedJob.id.slice(0, 8)}…` }),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: `Cancel OCR job ${queuedJob.id.slice(0, 8)}…` }),
    );
    await waitFor(() => expect(cancelOCRJobMock).toHaveBeenCalledWith("job-queued-1"));
  });

  it("does not show the cancel action without the ocr_jobs:cancel permission", async () => {
    listOCRJobsMock.mockResolvedValueOnce(jobPage([queuedJob]));
    listOCRProvidersMock.mockResolvedValueOnce(providerPage(providers));
    renderPage([]);

    await screen.findByText("Tesseract OCR");
    expect(
      screen.queryByRole("button", { name: `Cancel OCR job ${queuedJob.id.slice(0, 8)}…` }),
    ).not.toBeInTheDocument();
  });

  it("navigates to the OCR job details screen when View is clicked", async () => {
    listOCRJobsMock.mockResolvedValueOnce(jobPage([queuedJob]));
    listOCRProvidersMock.mockResolvedValueOnce(providerPage(providers));
    renderPage(["ocr_jobs:cancel"]);

    await screen.findByText("Tesseract OCR");
    await userEvent.click(screen.getByRole("button", { name: `View OCR job ${queuedJob.id.slice(0, 8)}…` }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/ocr-jobs/job-queued-1");
  });
});
