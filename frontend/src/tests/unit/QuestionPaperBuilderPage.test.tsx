import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { QuestionPaperBuilderPage } from "@/pages/assessment/QuestionPaperBuilderPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type {
  Assessment,
  Question,
  QuestionPaper,
  QuestionPaperQuestionMapping,
  QuestionPaperSection,
} from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  listMock,
  createMock,
  updateMock,
  removeMock,
  assessmentsListMock,
  blueprintsListMock,
  templatesListMock,
  sectionsListMock,
  sectionsCreateMock,
  sectionsUpdateMock,
  sectionsRemoveMock,
  mappingsListMock,
  mappingsCreateMock,
  mappingsUpdateMock,
  mappingsRemoveMock,
  questionsListMock,
  randomizationCreateMock,
  submitMock,
  approveMock,
  rejectMock,
  snapshotMock,
} = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  assessmentsListMock: vi.fn(),
  blueprintsListMock: vi.fn(),
  templatesListMock: vi.fn(),
  sectionsListMock: vi.fn(),
  sectionsCreateMock: vi.fn(),
  sectionsUpdateMock: vi.fn(),
  sectionsRemoveMock: vi.fn(),
  mappingsListMock: vi.fn(),
  mappingsCreateMock: vi.fn(),
  mappingsUpdateMock: vi.fn(),
  mappingsRemoveMock: vi.fn(),
  questionsListMock: vi.fn(),
  randomizationCreateMock: vi.fn(),
  submitMock: vi.fn(),
  approveMock: vi.fn(),
  rejectMock: vi.fn(),
  snapshotMock: vi.fn(),
}));

vi.mock("@/api/questionPapers", () => ({
  questionPapersApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
    restore: vi.fn(),
  },
  submitQuestionPaperForReview: submitMock,
  approveQuestionPaper: approveMock,
  rejectQuestionPaper: rejectMock,
  createQuestionPaperVersionSnapshot: snapshotMock,
}));

vi.mock("@/api/assessments", () => ({
  assessmentsApi: {
    list: assessmentsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionBlueprints", () => ({
  questionBlueprintsApi: {
    list: blueprintsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionPaperTemplates", () => ({
  questionPaperTemplatesApi: {
    list: templatesListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionPaperSections", () => ({
  questionPaperSectionsApi: {
    list: sectionsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: sectionsCreateMock,
    update: sectionsUpdateMock,
    remove: sectionsRemoveMock,
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionPaperQuestionMappings", () => ({
  questionPaperQuestionMappingsApi: {
    list: mappingsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: mappingsCreateMock,
    update: mappingsUpdateMock,
    remove: mappingsRemoveMock,
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questions", () => ({
  questionsApi: {
    list: questionsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
  submitQuestionForReview: vi.fn(),
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
  addQuestionTag: vi.fn(),
  removeQuestionTag: vi.fn(),
  createQuestionVersionSnapshot: vi.fn(),
}));

vi.mock("@/api/randomizationStrategies", () => ({
  randomizationStrategiesApi: {
    list: vi.fn(),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: randomizationCreateMock,
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
  permissions: [
    "question_papers:create",
    "question_papers:read",
    "question_papers:update",
    "question_papers:delete",
    "question_papers:approve",
    "question_papers:reject",
    "question_paper_sections:create",
    "question_paper_sections:read",
    "question_paper_sections:update",
    "question_paper_sections:delete",
    "question_paper_question_mappings:create",
    "question_paper_question_mappings:read",
    "question_paper_question_mappings:update",
    "question_paper_question_mappings:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const assessment: Assessment = {
  id: "assessment-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  assessment_type_id: "assessment-type-1",
  assessment_status_id: "assessment-status-1",
  name: "Midterm Assessment",
  description: null,
  is_active: true,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const paper: QuestionPaper = {
  id: "paper-1",
  institution_id: "inst-1",
  assessment_id: "assessment-1",
  blueprint_id: null,
  template_id: null,
  name: "Midterm Paper A",
  total_marks: "100.00",
  is_active: true,
  current_version: 1,
  approval_status: "draft",
  approved_by: null,
  approved_at: null,
  rejection_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const section: QuestionPaperSection = {
  id: "section-1",
  institution_id: "inst-1",
  question_paper_id: "paper-1",
  name: "Section A",
  instructions: null,
  marks_per_question: null,
  display_order: 0,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const question: Question = {
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
  approval_status: "approved",
  approved_by: null,
  approved_at: null,
  rejection_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const pendingPaper: QuestionPaper = {
  ...paper,
  id: "paper-2",
  name: "Pending Paper",
  approval_status: "pending_review",
};

const mapping: QuestionPaperQuestionMapping = {
  id: "mapping-1",
  institution_id: "inst-1",
  question_paper_section_id: "section-1",
  question_id: "question-1",
  order_index: 1,
  marks_override: null,
  is_optional: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page<T>(items: T[]): Page<T> {
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
            <QuestionPaperBuilderPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionPaperBuilderPage", () => {
  beforeEach(() => {
    // Shared select-options fetches used across every test.
    assessmentsListMock.mockResolvedValue(page([assessment]));
    blueprintsListMock.mockResolvedValue(page([]));
    templatesListMock.mockResolvedValue(page([]));
    questionsListMock.mockResolvedValue(page([question]));
  });

  it("lists question papers", async () => {
    listMock.mockResolvedValueOnce(page([paper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    renderPage();

    expect(await screen.findByText("Midterm Paper A")).toBeInTheDocument();
    expect(screen.getByText("Midterm Assessment")).toBeInTheDocument();
  });

  it("creates a question paper", async () => {
    listMock.mockResolvedValue(page([]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(paper);
    renderPage();

    await screen.findByText("No question papers found.");
    await userEvent.click(screen.getByRole("button", { name: "New Question Paper" }));

    await screen.findByText("Select an assessment");
    await userEvent.selectOptions(screen.getByLabelText(/^Assessment/), "assessment-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Midterm Paper A");
    const totalMarksInput = screen.getByLabelText(/^Total Marks/);
    await userEvent.clear(totalMarksInput);
    await userEvent.type(totalMarksInput, "100");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ assessment_id: "assessment-1", name: "Midterm Paper A" }),
      ),
    );
  });

  it("drills down from papers to sections to question mappings", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([section]));
    mappingsListMock.mockResolvedValue(page([]));
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(screen.getByRole("button", { name: "Manage sections for Midterm Paper A" }));

    expect(await screen.findByText('Sections for "Midterm Paper A"')).toBeInTheDocument();
    await screen.findByText("Section A");

    await userEvent.click(screen.getByRole("button", { name: "Manage questions for Section A" }));

    expect(await screen.findByText('Questions in "Section A"')).toBeInTheDocument();
    expect(screen.getByText("No question mappings found.")).toBeInTheDocument();
  });

  it("edits a question paper", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    updateMock.mockResolvedValueOnce({ ...paper, name: "Midterm Paper B" });
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(screen.getByRole("button", { name: "Edit Midterm Paper A" }));

    const nameInput = await screen.findByLabelText(/^Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Midterm Paper B");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        "paper-1",
        expect.objectContaining({ name: "Midterm Paper B" }),
      ),
    );
  });

  it("deletes a question paper", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(screen.getByRole("button", { name: "Delete Midterm Paper A" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("paper-1"));
  });

  it("submits a draft question paper for review", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    submitMock.mockResolvedValueOnce({ ...paper, approval_status: "pending_review" });
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(screen.getByRole("button", { name: "Submit for Review" }));

    await waitFor(() => expect(submitMock).toHaveBeenCalledWith("paper-1"));
  });

  it("approves a question paper pending review", async () => {
    listMock.mockResolvedValue(page([pendingPaper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    approveMock.mockResolvedValueOnce({ ...pendingPaper, approval_status: "approved" });
    renderPage();

    await screen.findByText("Pending Paper");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(approveMock).toHaveBeenCalledWith("paper-2"));
  });

  it("rejects a question paper with a reason", async () => {
    listMock.mockResolvedValue(page([pendingPaper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    rejectMock.mockResolvedValueOnce({ ...pendingPaper, approval_status: "rejected" });
    renderPage();

    await screen.findByText("Pending Paper");
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Missing rubric alignment");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

    await waitFor(() =>
      expect(rejectMock).toHaveBeenCalledWith("paper-2", { reason: "Missing rubric alignment" }),
    );
  });

  it("creates a version snapshot with a change reason", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    snapshotMock.mockResolvedValueOnce({ ...paper, current_version: 2 });
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(screen.getByRole("button", { name: "Version Snapshot" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Change Reason/), "Fixed typo");
    await userEvent.click(within(dialog).getByRole("button", { name: "Create Snapshot" }));

    await waitFor(() =>
      expect(snapshotMock).toHaveBeenCalledWith("paper-1", { change_reason: "Fixed typo" }),
    );
  });

  it("creates a randomization strategy for a question paper", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([]));
    mappingsListMock.mockResolvedValue(page([]));
    randomizationCreateMock.mockResolvedValueOnce({
      id: "strategy-1",
      institution_id: "inst-1",
      question_paper_id: "paper-1",
      question_paper_section_id: null,
      strategy_type: "shuffle_questions",
      config: null,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(
      screen.getByRole("button", { name: "Randomization for Midterm Paper A" }),
    );

    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(
      within(dialog).getByLabelText(/Strategy Type/),
      "shuffle_questions",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(randomizationCreateMock).toHaveBeenCalledWith({
        question_paper_id: "paper-1",
        strategy_type: "shuffle_questions",
      }),
    );
  });

  it("edits a section", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([section]));
    mappingsListMock.mockResolvedValue(page([]));
    sectionsUpdateMock.mockResolvedValueOnce({ ...section, name: "Section B" });
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage sections for Midterm Paper A" }),
    );
    await screen.findByText("Section A");

    await userEvent.click(screen.getByRole("button", { name: "Edit section Section A" }));
    const nameInput = await screen.findByLabelText(/^Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Section B");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(sectionsUpdateMock).toHaveBeenCalledWith(
        "section-1",
        expect.objectContaining({ name: "Section B" }),
      ),
    );
  });

  it("deletes a section", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([section]));
    mappingsListMock.mockResolvedValue(page([]));
    sectionsRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage sections for Midterm Paper A" }),
    );
    await screen.findByText("Section A");

    await userEvent.click(screen.getByRole("button", { name: "Delete section Section A" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(sectionsRemoveMock).toHaveBeenCalledWith("section-1"));
  });

  it("edits a question mapping", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([section]));
    mappingsListMock.mockResolvedValue(page([mapping]));
    mappingsUpdateMock.mockResolvedValueOnce({ ...mapping, order_index: 2 });
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage sections for Midterm Paper A" }),
    );
    await screen.findByText("Section A");
    await userEvent.click(screen.getByRole("button", { name: "Manage questions for Section A" }));
    await screen.findByText("What is the capital of France?");

    await userEvent.click(screen.getByRole("button", { name: "Edit mapping 1" }));
    const orderInput = await screen.findByLabelText(/^Order/);
    await userEvent.clear(orderInput);
    await userEvent.type(orderInput, "2");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(mappingsUpdateMock).toHaveBeenCalledWith(
        "mapping-1",
        expect.objectContaining({ order_index: 2 }),
      ),
    );
  });

  it("deletes a question mapping", async () => {
    listMock.mockResolvedValue(page([paper]));
    sectionsListMock.mockResolvedValue(page([section]));
    mappingsListMock.mockResolvedValue(page([mapping]));
    mappingsRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Paper A");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage sections for Midterm Paper A" }),
    );
    await screen.findByText("Section A");
    await userEvent.click(screen.getByRole("button", { name: "Manage questions for Section A" }));
    await screen.findByText("What is the capital of France?");

    await userEvent.click(screen.getByRole("button", { name: "Delete mapping 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mappingsRemoveMock).toHaveBeenCalledWith("mapping-1"));
  });
});
