import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AssessmentDashboardPage } from "@/pages/assessment/AssessmentDashboardPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Assessment, AssessmentStatus, AssessmentType } from "@/types/assessment";
import type { Subject } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, createMock, updateMock, removeMock, subjectsListMock, typesListMock, statusesListMock } =
  vi.hoisted(() => ({
    listMock: vi.fn(),
    createMock: vi.fn(),
    updateMock: vi.fn(),
    removeMock: vi.fn(),
    subjectsListMock: vi.fn(),
    typesListMock: vi.fn(),
    statusesListMock: vi.fn(),
  }));

vi.mock("@/api/assessments", () => ({
  assessmentsApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/subjects", () => ({
  subjectsApi: { list: subjectsListMock },
}));
vi.mock("@/api/assessmentTypes", () => ({
  assessmentTypesApi: { list: typesListMock },
}));
vi.mock("@/api/assessmentStatuses", () => ({
  assessmentStatusesApi: { list: statusesListMock },
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
  permissions: ["assessments:create", "assessments:read", "assessments:update", "assessments:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const subject: Subject = {
  id: "subj-1",
  institution_id: "inst-1",
  course_id: "course-1",
  subject_category_id: "cat-1",
  code: "CS101",
  name: "Data Structures",
  credits: "4.0",
  semester_number: 1,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const assessmentType: AssessmentType = {
  id: "type-1",
  institution_id: "inst-1",
  code: "MIDTERM",
  name: "Midterm",
  description: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const assessmentStatus: AssessmentStatus = {
  id: "status-1",
  institution_id: "inst-1",
  code: "OPEN",
  name: "Open",
  description: null,
  is_terminal: false,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const assessment: Assessment = {
  id: "assess-1",
  institution_id: "inst-1",
  subject_id: "subj-1",
  assessment_type_id: "type-1",
  assessment_status_id: "status-1",
  name: "Midterm Exam",
  description: null,
  is_active: true,
  current_version: 1,
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
            <AssessmentDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AssessmentDashboardPage", () => {
  beforeEach(() => {
    subjectsListMock.mockResolvedValue(page([subject]));
    typesListMock.mockResolvedValue(page([assessmentType]));
    statusesListMock.mockResolvedValue(page([assessmentStatus]));
  });

  it("lists assessments with resolved subject/type/status labels", async () => {
    listMock.mockResolvedValueOnce(page([assessment]));
    renderPage();

    expect(await screen.findByText("Midterm Exam")).toBeInTheDocument();
    expect(await screen.findByText("Data Structures")).toBeInTheDocument();
    expect(screen.getByText("Midterm")).toBeInTheDocument();
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
  });

  it("creates an assessment", async () => {
    listMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(assessment);
    renderPage();

    await screen.findByText("No assessments found.");
    await userEvent.click(screen.getByRole("button", { name: "New Assessment" }));

    await screen.findByText("Select a subject");
    await userEvent.selectOptions(screen.getByLabelText(/^Subject/), "subj-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Assessment Type/), "type-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Assessment Status/), "status-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          subject_id: "subj-1",
          assessment_type_id: "type-1",
          assessment_status_id: "status-1",
          name: "Midterm Exam",
        }),
      ),
    );
  });

  it("edits an assessment", async () => {
    listMock.mockResolvedValue(page([assessment]));
    updateMock.mockResolvedValueOnce({ ...assessment, name: "Updated Exam" });
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Edit Midterm Exam" }));

    const nameInput = await screen.findByLabelText(/^Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Updated Exam");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        "assess-1",
        expect.objectContaining({ name: "Updated Exam" }),
      ),
    );
  });

  it("deletes an assessment after confirmation", async () => {
    listMock.mockResolvedValue(page([assessment]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Exam");
    await userEvent.click(screen.getByRole("button", { name: "Delete Midterm Exam" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("assess-1"));
  });
});
