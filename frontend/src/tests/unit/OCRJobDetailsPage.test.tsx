import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { OCRJobDetailsPage } from "@/pages/ocr/OCRJobDetailsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { OCRJob, OCRProvider } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { getMock, cancelMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  cancelMock: vi.fn(),
}));
vi.mock("@/api/ocrJobs", () => ({
  getOCRJob: getMock,
  cancelOCRJob: cancelMock,
  listOCRJobs: vi.fn(),
  createOCRJob: vi.fn(),
}));

const { providersListMock } = vi.hoisted(() => ({
  providersListMock: vi.fn(),
}));
vi.mock("@/api/ocrProviders", () => ({
  listOCRProviders: providersListMock,
  getOCRProvider: vi.fn(),
  updateOCRProvider: vi.fn(),
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
  permissions: ["ocr_jobs:cancel"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const provider: OCRProvider = {
  id: "provider-1",
  code: "tesseract",
  name: "Tesseract",
  description: null,
  is_enabled: true,
  is_implemented: true,
  is_default: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const azureProvider: OCRProvider = {
  id: "provider-2",
  code: "azure_ocr",
  name: "Azure Document Intelligence",
  description: null,
  is_enabled: true,
  is_implemented: true,
  is_default: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const job: OCRJob = {
  id: "job-1",
  institution_id: "inst-1",
  answer_script_id: "script-1",
  ocr_provider_id: "provider-1",
  requested_ocr_provider_id: null,
  fallback_reason: null,
  celery_task_id: "task-abc",
  status: "running",
  priority: 5,
  retry_count: 1,
  max_retries: 3,
  started_at: "2026-01-01T00:00:00Z",
  completed_at: null,
  error_message: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function providerPage(items: OCRProvider[]): Page<OCRProvider> {
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
        <MemoryRouter initialEntries={["/dashboard/ocr-jobs/job-1"]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/ocr-jobs/:id" element={<OCRJobDetailsPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("OCRJobDetailsPage", () => {
  it("renders job detail fields correctly", async () => {
    getMock.mockResolvedValueOnce(job);
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage();

    expect(await screen.findByText("Tesseract")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument();
    expect(screen.getByText("task-abc")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("cancels the job when Cancel is clicked", async () => {
    getMock.mockResolvedValue(job);
    providersListMock.mockResolvedValue(providerPage([provider]));
    cancelMock.mockResolvedValueOnce({ ...job, status: "cancelled" });
    renderPage();

    await screen.findByText("Tesseract");
    await userEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    await waitFor(() => expect(cancelMock).toHaveBeenCalledWith("job-1"));
  });

  it("does not show the Cancel button for a completed job", async () => {
    getMock.mockResolvedValueOnce({ ...job, status: "completed" });
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage();

    await screen.findByText("Tesseract");
    expect(screen.queryByRole("button", { name: /Cancel/ })).not.toBeInTheDocument();
  });

  it("shows the error message alert when present", async () => {
    getMock.mockResolvedValueOnce({ ...job, status: "failed", error_message: "Provider timed out." });
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage();

    expect(await screen.findByText("Provider timed out.")).toBeInTheDocument();
  });

  it("shows a fallback banner when the job fell back to a different provider", async () => {
    getMock.mockResolvedValueOnce({
      ...job,
      ocr_provider_id: "provider-1",
      requested_ocr_provider_id: "provider-2",
      fallback_reason: "Azure Document Intelligence requires both an endpoint and an API key.",
    });
    providersListMock.mockResolvedValueOnce(providerPage([provider, azureProvider]));
    renderPage();

    expect(await screen.findByText("Provider Fallback")).toBeInTheDocument();
    expect(
      screen.getByText("Azure Document Intelligence requires both an endpoint and an API key."),
    ).toBeInTheDocument();
  });

  it("does not show a fallback banner when no fallback happened", async () => {
    getMock.mockResolvedValueOnce(job);
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage();

    await screen.findByText("Tesseract");
    expect(screen.queryByText("Provider Fallback")).not.toBeInTheDocument();
  });
});
