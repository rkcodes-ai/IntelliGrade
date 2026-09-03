import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { ExamManagementPage } from "@/pages/assessment/ExamManagementPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Section } from "@/types/academic";
import type { Assessment, Exam, ExamInstructions } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  examListMock,
  examCreateMock,
  examUpdateMock,
  examRemoveMock,
  assessmentListMock,
  sectionListMock,
  instructionListMock,
  instructionCreateMock,
  instructionUpdateMock,
  instructionRemoveMock,
} = vi.hoisted(() => ({
  examListMock: vi.fn(),
  examCreateMock: vi.fn(),
  examUpdateMock: vi.fn(),
  examRemoveMock: vi.fn(),
  assessmentListMock: vi.fn(),
  sectionListMock: vi.fn(),
  instructionListMock: vi.fn(),
  instructionCreateMock: vi.fn(),
  instructionUpdateMock: vi.fn(),
  instructionRemoveMock: vi.fn(),
}));

vi.mock("@/api/exams", () => ({
  examsApi: {
    list: examListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: examCreateMock,
    update: examUpdateMock,
    remove: examRemoveMock,
    restore: vi.fn(),
  },
}));

vi.mock("@/api/assessments", () => ({
  assessmentsApi: {
    list: assessmentListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/sections", () => ({
  sectionsApi: {
    list: sectionListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/examInstructions", () => ({
  examInstructionsApi: {
    list: instructionListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: instructionCreateMock,
    update: instructionUpdateMock,
    remove: instructionRemoveMock,
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
    "exams:create",
    "exams:read",
    "exams:update",
    "exams:delete",
    "exam_instructions:create",
    "exam_instructions:read",
    "exam_instructions:update",
    "exam_instructions:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const assessment: Assessment = {
  id: "assessment-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  assessment_type_id: "type-1",
  assessment_status_id: "status-1",
  name: "Midterm Assessment",
  description: null,
  is_active: true,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const section: Section = {
  id: "section-1",
  institution_id: "inst-1",
  batch_id: "batch-1",
  name: "Section A",
  max_capacity: 40,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const exam: Exam = {
  id: "exam-1",
  institution_id: "inst-1",
  assessment_id: "assessment-1",
  section_id: "section-1",
  name: "Midterm Exam",
  exam_date: "2026-08-01",
  is_active: true,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const instruction: ExamInstructions = {
  id: "instruction-1",
  institution_id: "inst-1",
  exam_id: "exam-1",
  instructions_text: "Bring your ID card.",
  display_order: 1,
  is_active: true,
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
            <ExamManagementPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ExamManagementPage", () => {
  it("lists exams for the current institution", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    renderPage();

    expect(await screen.findByText("Midterm Exam")).toBeInTheDocument();
    expect(await screen.findByText("Midterm Assessment")).toBeInTheDocument();
    expect(screen.getByText("Section A")).toBeInTheDocument();
  });

  it("creates an exam", async () => {
    examListMock.mockResolvedValue(page([]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    examCreateMock.mockResolvedValueOnce(exam);
    renderPage();

    await screen.findByText("No exams found.");
    await userEvent.click(screen.getByRole("button", { name: "New Exam" }));
    await userEvent.selectOptions(screen.getByLabelText(/^Assessment/), "assessment-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Section/), "section-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Midterm Exam");
    await userEvent.type(screen.getByLabelText(/^Exam Date/), "2026-08-01");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(examCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          assessment_id: "assessment-1",
          section_id: "section-1",
          name: "Midterm Exam",
          exam_date: "2026-08-01",
        }),
      ),
    );
  });

  it("deletes an exam after confirmation", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    examRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Delete Midterm Exam" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(examRemoveMock).toHaveBeenCalledWith("exam-1"));
  });

  it("opens the nested instructions panel for a selected exam", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Manage instructions for Midterm Exam" }));

    expect(await screen.findByText('Instructions for "Midterm Exam"')).toBeInTheDocument();
  });

  it("edits an exam", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    examUpdateMock.mockResolvedValueOnce({ ...exam, name: "Final Exam" });
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Edit Midterm Exam" }));

    const nameInput = screen.getByLabelText(/^Name/);
    expect(nameInput).toHaveValue("Midterm Exam");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Final Exam");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(examUpdateMock).toHaveBeenCalledWith(
        "exam-1",
        expect.objectContaining({ name: "Final Exam" }),
      ),
    );
  });

  it("creates an exam instruction from within the nested panel", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    instructionCreateMock.mockResolvedValueOnce(instruction);
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Manage instructions for Midterm Exam" }));
    await screen.findByText('Instructions for "Midterm Exam"');
    await screen.findByText("No instructions found.");

    await userEvent.click(screen.getByRole("button", { name: "New Instruction" }));
    await userEvent.type(screen.getByLabelText(/^Instructions/), "Bring your ID card.");
    const orderInput = screen.getByLabelText(/^Display Order/);
    await userEvent.clear(orderInput);
    await userEvent.type(orderInput, "1");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(instructionCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          exam_id: "exam-1",
          instructions_text: "Bring your ID card.",
          display_order: 1,
        }),
      ),
    );
  });

  it("edits an exam instruction from within the nested panel", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page([instruction]));
    instructionUpdateMock.mockResolvedValueOnce({ ...instruction, instructions_text: "Updated text." });
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Manage instructions for Midterm Exam" }));
    await screen.findByText("Bring your ID card.");

    await userEvent.click(screen.getByRole("button", { name: "Edit instruction 1" }));
    const textArea = screen.getByLabelText(/^Instructions/);
    expect(textArea).toHaveValue("Bring your ID card.");
    await userEvent.clear(textArea);
    await userEvent.type(textArea, "Updated text.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(instructionUpdateMock).toHaveBeenCalledWith(
        "instruction-1",
        expect.objectContaining({ instructions_text: "Updated text." }),
      ),
    );
  });

  it("deletes an exam instruction after confirmation", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page([instruction]));
    instructionRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Manage instructions for Midterm Exam" }));
    await screen.findByText("Bring your ID card.");

    await userEvent.click(screen.getByRole("button", { name: "Delete instruction 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(instructionRemoveMock).toHaveBeenCalledWith("instruction-1"));
  });

  it("returns to the exam list from the nested instructions panel", async () => {
    examListMock.mockResolvedValue(page([exam]));
    assessmentListMock.mockResolvedValue(page([assessment]));
    sectionListMock.mockResolvedValue(page([section]));
    instructionListMock.mockResolvedValue(page<ExamInstructions>([]));
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Manage instructions for Midterm Exam" }));
    await screen.findByText('Instructions for "Midterm Exam"');

    await userEvent.click(screen.getByRole("button", { name: "Back to exams" }));
    expect(screen.queryByText('Instructions for "Midterm Exam"')).not.toBeInTheDocument();
  });
});
