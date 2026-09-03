import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { QuestionViewerPage } from "@/pages/assessment/QuestionViewerPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Question } from "@/types/assessment";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const {
  getMock,
  submitQuestionForReviewMock,
  addQuestionTagMock,
  removeQuestionTagMock,
  createQuestionVersionSnapshotMock,
  tagsListMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  submitQuestionForReviewMock: vi.fn(),
  addQuestionTagMock: vi.fn(),
  removeQuestionTagMock: vi.fn(),
  createQuestionVersionSnapshotMock: vi.fn(),
  tagsListMock: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 }),
}));
vi.mock("@/api/questions", () => ({
  questionsApi: {
    list: vi.fn(),
    listDeleted: vi.fn(),
    get: getMock,
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
  submitQuestionForReview: submitQuestionForReviewMock,
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
  addQuestionTag: addQuestionTagMock,
  removeQuestionTag: removeQuestionTagMock,
  createQuestionVersionSnapshot: createQuestionVersionSnapshotMock,
}));

vi.mock("@/api/questionTags", () => ({
  questionTagsApi: {
    list: tagsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/subjects", () => ({
  subjectsApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: "subject-1", name: "Mathematics" }],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    }),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionCategories", () => ({
  questionCategoriesApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: "category-1", name: "Algebra" }],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    }),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionTypes", () => ({
  questionTypesApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: "type-1", name: "Multiple Choice" }],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    }),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/difficultyLevels", () => ({
  difficultyLevelsApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: "difficulty-1", name: "Easy" }],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    }),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/bloomTaxonomyLevels", () => ({
  bloomTaxonomyLevelsApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: "bloom-1", name: "Remember" }],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    }),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
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
  permissions: ["questions:create", "questions:read", "questions:update"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const question: Question = {
  id: "q-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  question_category_id: "category-1",
  question_type_id: "type-1",
  difficulty_level_id: "difficulty-1",
  bloom_level_id: "bloom-1",
  unit: "Unit 1",
  chapter: "Chapter 1",
  topic: "Linear Equations",
  subtopic: "Slope-intercept form",
  learning_outcome: "Solve linear equations",
  question_text: "What is the value of x in 2x + 4 = 10?",
  estimated_time_minutes: 5,
  marks: "5.00",
  language: "en",
  attachments: null,
  diagram_url: null,
  question_metadata: null,
  is_active: true,
  current_version: 1,
  approval_status: "draft",
  approved_by: null,
  approved_at: null,
  rejection_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

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
        <MemoryRouter initialEntries={["/dashboard/questions/q-1"]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/questions/:id" element={<QuestionViewerPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionViewerPage", () => {
  it("renders question detail fields correctly for a fetched question", async () => {
    getMock.mockResolvedValueOnce(question);
    renderPage();

    expect(await screen.findByText("What is the value of x in 2x + 4 = 10?")).toBeInTheDocument();
    expect(screen.getByText("Version v1")).toBeInTheDocument();
    expect(screen.getByText("draft")).toBeInTheDocument();
    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("Algebra")).toBeInTheDocument();
    expect(screen.getByText("Multiple Choice")).toBeInTheDocument();
    expect(screen.getByText("Easy")).toBeInTheDocument();
    expect(screen.getByText("Remember")).toBeInTheDocument();
    expect(screen.getByText("5.00")).toBeInTheDocument();
  });

  it("navigates to the edit route when Edit is clicked", async () => {
    getMock.mockResolvedValueOnce(question);
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    await userEvent.click(screen.getByRole("button", { name: /Edit/ }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/questions/q-1/edit");
  });

  it("calls submitQuestionForReview when Submit for Review is clicked", async () => {
    getMock.mockResolvedValue(question);
    submitQuestionForReviewMock.mockResolvedValueOnce({ ...question, approval_status: "pending_review" });
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    await userEvent.click(screen.getByRole("button", { name: /Submit for Review/ }));
    expect(submitQuestionForReviewMock).toHaveBeenCalledWith("q-1");
  });

  it("navigates to the reviews route when View Reviews is clicked", async () => {
    getMock.mockResolvedValueOnce(question);
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    await userEvent.click(screen.getByRole("button", { name: /View Reviews/ }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/questions/q-1/reviews");
  });

  it("opens the version snapshot dialog and submits with a change reason", async () => {
    getMock.mockResolvedValue(question);
    createQuestionVersionSnapshotMock.mockResolvedValueOnce({
      id: "snapshot-1",
      question_id: "q-1",
      version_number: 2,
      change_reason: "Fixed a typo.",
    });
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    await userEvent.click(screen.getByRole("button", { name: /Create Version Snapshot/ }));

    const reasonInput = await screen.findByLabelText(/^Change Reason/);
    await userEvent.type(reasonInput, "Fixed a typo.");
    await userEvent.click(screen.getByRole("button", { name: "Create Snapshot" }));

    await waitFor(() =>
      expect(createQuestionVersionSnapshotMock).toHaveBeenCalledWith("q-1", {
        change_reason: "Fixed a typo.",
      }),
    );
  });

  it("submits a version snapshot with an undefined change reason when left blank", async () => {
    getMock.mockResolvedValue(question);
    createQuestionVersionSnapshotMock.mockResolvedValueOnce({
      id: "snapshot-2",
      question_id: "q-1",
      version_number: 2,
      change_reason: null,
    });
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    await userEvent.click(screen.getByRole("button", { name: /Create Version Snapshot/ }));
    await screen.findByLabelText(/^Change Reason/);
    await userEvent.click(screen.getByRole("button", { name: "Create Snapshot" }));

    await waitFor(() =>
      expect(createQuestionVersionSnapshotMock).toHaveBeenCalledWith("q-1", {
        change_reason: undefined,
      }),
    );
  });

  it("adds a tag via the select and Add button", async () => {
    getMock.mockResolvedValue(question);
    tagsListMock.mockResolvedValueOnce({
      items: [
        { id: "tag-1", institution_id: "inst-1", name: "Algebra Basics", description: null, is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
        { id: "tag-2", institution_id: "inst-1", name: "Geometry Basics", description: null, is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      ],
      total: 2,
      page: 1,
      page_size: 200,
      total_pages: 1,
    });
    addQuestionTagMock.mockResolvedValueOnce({
      id: "map-1",
      institution_id: "inst-1",
      question_id: "q-1",
      tag_id: "tag-1",
      created_at: "2026-01-01T00:00:00Z",
    });
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    expect(screen.getByText("No tags added yet.")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Select tag to add"), "tag-1");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(addQuestionTagMock).toHaveBeenCalledWith("q-1", { tag_id: "tag-1" }));
    expect(await screen.findByRole("button", { name: "Remove tag Algebra Basics" })).toBeInTheDocument();
    expect(screen.queryByText("No tags added yet.")).not.toBeInTheDocument();
  });

  it("removes a previously-added tag", async () => {
    getMock.mockResolvedValue(question);
    tagsListMock.mockResolvedValueOnce({
      items: [
        { id: "tag-1", institution_id: "inst-1", name: "Algebra Basics", description: null, is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      ],
      total: 1,
      page: 1,
      page_size: 200,
      total_pages: 1,
    });
    addQuestionTagMock.mockResolvedValueOnce({
      id: "map-1",
      institution_id: "inst-1",
      question_id: "q-1",
      tag_id: "tag-1",
      created_at: "2026-01-01T00:00:00Z",
    });
    removeQuestionTagMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    await userEvent.selectOptions(screen.getByLabelText("Select tag to add"), "tag-1");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await screen.findByRole("button", { name: "Remove tag Algebra Basics" });

    await userEvent.click(screen.getByRole("button", { name: "Remove tag Algebra Basics" }));

    await waitFor(() => expect(removeQuestionTagMock).toHaveBeenCalledWith("q-1", "tag-1"));
    expect(await screen.findByText("No tags added yet.")).toBeInTheDocument();
  });

  it("renders the approved badge styling for an approved question", async () => {
    getMock.mockResolvedValueOnce({ ...question, approval_status: "approved" });
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    const badge = screen.getByText("approved");
    expect(badge).toHaveClass("bg-success/10", "text-success");
  });

  it("renders the rejected badge styling for a rejected question", async () => {
    getMock.mockResolvedValueOnce({ ...question, approval_status: "rejected" });
    renderPage();

    await screen.findByText("What is the value of x in 2x + 4 = 10?");
    const badge = screen.getByText("rejected");
    expect(badge).toHaveClass("bg-destructive/10", "text-destructive");
  });
});
