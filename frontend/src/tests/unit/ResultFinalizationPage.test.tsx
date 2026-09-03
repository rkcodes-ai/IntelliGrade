import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { ResultFinalizationPage } from "@/pages/ocr/ResultFinalizationPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { ExamResult } from "@/types/teacherReview";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  listMock,
  finalizeStudentMock,
  finalizeExamMock,
  finalizeBatchMock,
  approveMock,
  lockMock,
  unlockMock,
  publishMock,
  bulkApproveMock,
  bulkLockMock,
  bulkPublishMock,
} = vi.hoisted(() => ({
  listMock: vi.fn(),
  finalizeStudentMock: vi.fn(),
  finalizeExamMock: vi.fn(),
  finalizeBatchMock: vi.fn(),
  approveMock: vi.fn(),
  lockMock: vi.fn(),
  unlockMock: vi.fn(),
  publishMock: vi.fn(),
  bulkApproveMock: vi.fn(),
  bulkLockMock: vi.fn(),
  bulkPublishMock: vi.fn(),
}));
vi.mock("@/api/examResults", () => ({
  listExamResults: listMock,
  getExamResult: vi.fn(),
  finalizeStudentResult: finalizeStudentMock,
  finalizeExamResults: finalizeExamMock,
  finalizeBatchResults: finalizeBatchMock,
  approveExamResult: approveMock,
  lockExamResult: lockMock,
  unlockExamResult: unlockMock,
  publishExamResult: publishMock,
  bulkApproveExamResults: bulkApproveMock,
  bulkLockExamResults: bulkLockMock,
  bulkPublishExamResults: bulkPublishMock,
}));

const ALL_PERMISSIONS = [
  "exam_results:finalize",
  "exam_results:approve",
  "exam_results:lock",
  "exam_results:publish",
  "exam_results:unlock",
];

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
  permissions: ALL_PERMISSIONS,
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeResult(overrides: Partial<ExamResult> = {}): ExamResult {
  return {
    id: "result-1",
    institution_id: "inst-1",
    exam_session_id: "session-1",
    status: "under_review",
    total_max_marks: "100",
    total_marks: "80",
    finalized_by: "user-1",
    finalized_at: "2026-01-01T00:00:00Z",
    approved_by: null,
    approved_at: null,
    locked_by: null,
    locked_at: null,
    published_by: null,
    published_at: null,
    unlocked_by: null,
    unlocked_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeResultsPage(overrides: Partial<Page<ExamResult>> = {}): Page<ExamResult> {
  return {
    items: [makeResult()],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    ...overrides,
  };
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
            <ResultFinalizationPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ResultFinalizationPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the exam results table with correct status text and marks", async () => {
    listMock.mockResolvedValue(
      makeResultsPage({
        items: [makeResult({ exam_session_id: "session-xyz", status: "under_review", total_marks: "80", total_max_marks: "100" })],
      }),
    );
    renderPage();

    expect(await screen.findByText("session-xyz")).toBeInTheDocument();
    expect(screen.getByText("under review")).toBeInTheDocument();
    expect(screen.getByText("80 / 100")).toBeInTheDocument();
  });

  it("shows Approve for under_review status with exam_results:approve permission", async () => {
    listMock.mockResolvedValue(makeResultsPage({ items: [makeResult({ status: "under_review" })] }));
    renderPage();

    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Lock" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unlock" })).not.toBeInTheDocument();
  });

  it("shows Lock for approved status with exam_results:lock permission", async () => {
    listMock.mockResolvedValue(makeResultsPage({ items: [makeResult({ status: "approved" })] }));
    renderPage();

    expect(await screen.findByRole("button", { name: "Lock" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("shows Unlock for locked and published statuses with exam_results:unlock permission, and confirms before unlocking", async () => {
    listMock.mockResolvedValue(makeResultsPage({ items: [makeResult({ id: "result-locked", status: "locked" })] }));
    unlockMock.mockResolvedValueOnce(makeResult({ id: "result-locked", status: "approved" }));
    renderPage();

    const unlockButton = await screen.findByRole("button", { name: "Unlock" });
    await userEvent.click(unlockButton);

    expect(await screen.findByText("Unlock this result? Further edits will be allowed again.")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Unlock" }));

    await waitFor(() => expect(unlockMock).toHaveBeenCalledWith("result-locked"));
    expect(await screen.findByText("Result unlocked.")).toBeInTheDocument();
  });

  it("hides Approve action when the exam_results:approve permission is absent", async () => {
    listMock.mockResolvedValue(makeResultsPage({ items: [makeResult({ status: "under_review" })] }));
    renderPage({ ...baseUser, permissions: ["exam_results:finalize"] });

    await screen.findByText("session-1");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("finalizes a student result with the typed exam session id and shows a success toast", async () => {
    listMock.mockResolvedValue(makeResultsPage());
    finalizeStudentMock.mockResolvedValueOnce(makeResult());
    renderPage();

    await screen.findByRole("heading", { name: "Finalize Student" });
    await userEvent.type(screen.getByLabelText(/^Exam Session ID/), "session-42");
    await userEvent.click(screen.getByRole("button", { name: "Finalize Student" }));

    await waitFor(() =>
      expect(finalizeStudentMock).toHaveBeenCalledWith({ exam_session_id: "session-42" }),
    );
    expect(await screen.findByText("Student result finalized.")).toBeInTheDocument();
  });

  it("bulk approves exam results and shows a toast with succeeded/failed counts", async () => {
    listMock.mockResolvedValue(makeResultsPage());
    bulkApproveMock.mockResolvedValueOnce({
      succeeded_count: 7,
      failed: [{ reference_id: "session-9", reason: "already locked" }],
    });
    renderPage();

    await screen.findByText("Bulk Actions");
    await userEvent.type(screen.getByLabelText("Exam ID"), "exam-1");
    await userEvent.click(screen.getByRole("button", { name: "Bulk Approve" }));

    await waitFor(() => expect(bulkApproveMock).toHaveBeenCalledWith({ exam_id: "exam-1" }));
    expect(await screen.findByText("7 finalized, 1 failed")).toBeInTheDocument();
  });

  it("hides finalize forms and bulk actions when their permissions are absent", async () => {
    listMock.mockResolvedValue(makeResultsPage());
    renderPage({ ...baseUser, permissions: [] });

    await screen.findByText("session-1");
    expect(screen.queryByText("Finalize Student")).not.toBeInTheDocument();
    expect(screen.queryByText("Bulk Actions")).not.toBeInTheDocument();
  });
});
