import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { ReportsPage } from "@/pages/ocr/ReportsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Page } from "@/types/pagination";
import type { ReportJob } from "@/types/teacherReview";
import type { User } from "@/types/auth";

const { listMock, getMock, generateMock, downloadMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  getMock: vi.fn(),
  generateMock: vi.fn(),
  downloadMock: vi.fn(),
}));
vi.mock("@/api/reports", () => ({
  listReports: listMock,
  getReport: getMock,
  generateReport: generateMock,
  downloadReport: downloadMock,
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
  permissions: ["reports:read", "reports:generate"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeJob(overrides: Partial<ReportJob> = {}): ReportJob {
  return {
    id: "job-1",
    institution_id: "inst-1",
    report_type: "student",
    format: "pdf",
    parameters: null,
    requested_by: "user-1",
    status: "pending",
    storage_key: null,
    failure_reason: null,
    started_at: null,
    completed_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: ReportJob[]): Page<ReportJob> {
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
            <ReportsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ReportsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders report rows with the correct status text and failure reason", async () => {
    listMock.mockResolvedValueOnce(
      page([
        makeJob({ id: "job-pending", status: "pending" }),
        makeJob({ id: "job-processing", status: "processing", report_type: "question_wise" }),
        makeJob({ id: "job-completed", status: "completed", report_type: "ai_performance" }),
        makeJob({
          id: "job-failed",
          status: "failed",
          report_type: "teacher_review",
          failure_reason: "S3 upload timeout",
        }),
      ]),
    );
    renderPage();

    expect(await screen.findByText("pending")).toBeInTheDocument();
    expect(screen.getByText("processing")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("S3 upload timeout")).toBeInTheDocument();
    expect(screen.getByText("question wise")).toBeInTheDocument();
    expect(screen.getAllByText("PDF").length).toBeGreaterThan(0);
  });

  it("only shows Download for completed reports and opens the presigned url on click", async () => {
    listMock.mockResolvedValueOnce(
      page([
        makeJob({ id: "job-pending", status: "pending" }),
        makeJob({ id: "job-completed", status: "completed" }),
        makeJob({ id: "job-failed", status: "failed", failure_reason: "boom" }),
      ]),
    );
    downloadMock.mockResolvedValueOnce({ url: "https://storage.example.com/report-job-completed.pdf" });
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    renderPage();

    await screen.findByText("pending");
    const downloadButtons = screen.getAllByRole("button", { name: /Download report/ });
    expect(downloadButtons).toHaveLength(1);
    expect(downloadButtons[0]).toHaveAccessibleName("Download report job-completed");

    await userEvent.click(downloadButtons[0]);

    await waitFor(() => expect(downloadMock).toHaveBeenCalledWith("job-completed"));
    expect(openSpy).toHaveBeenCalledWith("https://storage.example.com/report-job-completed.pdf", "_blank");
  });

  it("hides the Generate Report action without the reports:generate permission", async () => {
    listMock.mockResolvedValueOnce(page([makeJob()]));
    renderPage({ ...baseUser, permissions: ["reports:read"] });

    await screen.findByText("pending");
    expect(screen.queryByRole("button", { name: "Generate Report" })).not.toBeInTheDocument();
  });

  it("submits the Generate Report dialog with parsed JSON parameters", async () => {
    listMock.mockResolvedValue(page([makeJob()]));
    generateMock.mockResolvedValueOnce(makeJob({ id: "job-new" }));
    renderPage();

    await screen.findByText("pending");
    await userEvent.click(screen.getByRole("button", { name: "Generate Report" }));

    const parametersInput = await screen.findByLabelText("Parameters (JSON)");
    fireEvent.change(parametersInput, { target: { value: '{"exam_id":"exam-1"}' } });
    await userEvent.click(screen.getByRole("button", { name: "Generate" }));

    await waitFor(() =>
      expect(generateMock).toHaveBeenCalledWith({
        report_type: "student",
        format: "pdf",
        parameters: { exam_id: "exam-1" },
      }),
    );
    expect(await screen.findByText("Report generation started.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate" })).not.toBeInTheDocument();
  });

  it("shows an error toast and does not submit when the parameters field has invalid JSON", async () => {
    listMock.mockResolvedValue(page([makeJob()]));
    renderPage();

    await screen.findByText("pending");
    await userEvent.click(screen.getByRole("button", { name: "Generate Report" }));

    const parametersInput = await screen.findByLabelText("Parameters (JSON)");
    fireEvent.change(parametersInput, { target: { value: "{not valid json" } });
    await userEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(
      await screen.findByText("Parameters must be valid JSON or left blank."),
    ).toBeInTheDocument();
    expect(generateMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Generate" })).toBeInTheDocument();
  });
});
