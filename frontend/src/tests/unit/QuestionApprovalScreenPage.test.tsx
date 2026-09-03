import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { QuestionApprovalScreenPage } from "@/pages/assessment/QuestionApprovalScreenPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Question, QuestionApproval } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, approveMock, rejectMock, listApprovalsMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  approveMock: vi.fn(),
  rejectMock: vi.fn(),
  listApprovalsMock: vi.fn(),
}));
vi.mock("@/api/questions", () => ({
  questionsApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
  approveQuestion: approveMock,
  rejectQuestion: rejectMock,
}));
vi.mock("@/api/questionApprovals", () => ({
  listQuestionApprovals: listApprovalsMock,
  getQuestionApproval: vi.fn(),
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
  permissions: ["questions:approve", "questions:reject"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const pendingQuestion: Question = {
  id: "question-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  question_category_id: "cat-1",
  question_type_id: "type-1",
  difficulty_level_id: "diff-1",
  bloom_level_id: "bloom-1",
  unit: null,
  chapter: null,
  topic: null,
  subtopic: null,
  learning_outcome: null,
  question_text: "What is the capital of France?",
  estimated_time_minutes: null,
  marks: "5.00",
  language: "en",
  attachments: null,
  diagram_url: null,
  question_metadata: null,
  is_active: true,
  current_version: 1,
  approval_status: "pending_review",
  approved_by: null,
  approved_at: null,
  rejection_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const approvedQuestion: Question = {
  ...pendingQuestion,
  id: "question-2",
  question_text: "Already approved question",
  approval_status: "approved",
};

const approvalRecord: QuestionApproval = {
  id: "approval-1",
  institution_id: "inst-1",
  question_id: "question-9",
  question_version_id: null,
  decision: "approved",
  reviewed_by: "user-2",
  reviewed_at: "2026-01-02T00:00:00Z",
  comments: "Looks good",
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function questionPage(items: Question[]): Page<Question> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
}

function approvalPage(items: QuestionApproval[]): Page<QuestionApproval> {
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
            <QuestionApprovalScreenPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionApprovalScreenPage", () => {
  it("lists only pending-review questions", async () => {
    listMock.mockResolvedValue(questionPage([pendingQuestion, approvedQuestion]));
    listApprovalsMock.mockResolvedValue(approvalPage([]));
    renderPage();

    expect(await screen.findByText("What is the capital of France?")).toBeInTheDocument();
    expect(screen.queryByText("Already approved question")).not.toBeInTheDocument();
  });

  it("approves a question", async () => {
    listMock.mockResolvedValue(questionPage([pendingQuestion]));
    listApprovalsMock.mockResolvedValue(approvalPage([]));
    approveMock.mockResolvedValueOnce({ ...pendingQuestion, approval_status: "approved" });
    renderPage();

    await screen.findByText("What is the capital of France?");
    await userEvent.click(
      screen.getByRole("button", { name: "Approve What is the capital of France?" }),
    );

    await waitFor(() => expect(approveMock).toHaveBeenCalledWith("question-1"));
  });

  it("rejects a question with a reason", async () => {
    listMock.mockResolvedValue(questionPage([pendingQuestion]));
    listApprovalsMock.mockResolvedValue(approvalPage([]));
    rejectMock.mockResolvedValueOnce({ ...pendingQuestion, approval_status: "rejected" });
    renderPage();

    await screen.findByText("What is the capital of France?");
    await userEvent.click(
      screen.getByRole("button", { name: "Reject What is the capital of France?" }),
    );
    await userEvent.type(screen.getByLabelText(/^Reason/), "Incorrect answer key");
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() =>
      expect(rejectMock).toHaveBeenCalledWith("question-1", { reason: "Incorrect answer key" }),
    );
  });

  it("renders approval history rows", async () => {
    listMock.mockResolvedValue(questionPage([]));
    listApprovalsMock.mockResolvedValue(approvalPage([approvalRecord]));
    renderPage();

    expect(await screen.findByText("question-9")).toBeInTheDocument();
    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getByText("Looks good")).toBeInTheDocument();
  });
});
