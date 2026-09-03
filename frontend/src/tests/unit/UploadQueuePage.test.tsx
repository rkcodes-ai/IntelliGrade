import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { UploadQueuePage } from "@/pages/ocr/UploadQueuePage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";
import type { UploadJob } from "@/types/ocr";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { listMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
}));
vi.mock("@/api/uploadJobs", () => ({
  listUploadJobs: listMock,
  getUploadJob: vi.fn(),
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

const runningJob: UploadJob = {
  id: "job-1",
  institution_id: "inst-1",
  answer_script_id: "script-11111111",
  upload_session_token: "token-1",
  total_chunks: 10,
  chunks_received: 4,
  bytes_received: 4096,
  total_bytes: null,
  status: "in_progress",
  retry_count: 0,
  failure_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const completedJob: UploadJob = {
  ...runningJob,
  id: "job-2",
  answer_script_id: "script-22222222",
  chunks_received: 10,
  bytes_received: 10240,
  total_bytes: 10240,
  status: "completed",
  retry_count: 1,
};

const failedJob: UploadJob = {
  ...runningJob,
  id: "job-3",
  answer_script_id: "script-33333333",
  total_chunks: 5,
  chunks_received: 2,
  status: "failed",
  retry_count: 3,
  failure_reason: "checksum mismatch",
};

function page(items: UploadJob[]): Page<UploadJob> {
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
            <UploadQueuePage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("UploadQueuePage", () => {
  it("lists upload jobs with status badges and progress", async () => {
    listMock.mockResolvedValueOnce(page([runningJob, completedJob, failedJob]));
    renderPage();

    expect(await screen.findByText("in progress")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("4/10 chunks")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("navigates to the answer script viewer when a row's script link is clicked", async () => {
    listMock.mockResolvedValueOnce(page([runningJob]));
    renderPage();

    await userEvent.click(await screen.findByText("script-1…"));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/answer-scripts/script-11111111");
  });

  it("shows an empty message when there are no upload jobs", async () => {
    listMock.mockResolvedValueOnce(page([]));
    renderPage();

    expect(await screen.findByText("No upload jobs found.")).toBeInTheDocument();
  });
});
