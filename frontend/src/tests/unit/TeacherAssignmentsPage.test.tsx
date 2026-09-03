import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { TeacherAssignmentsPage } from "@/pages/academic/TeacherAssignmentsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { SubjectAllocation, TeacherAssignment } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listAssignmentsMock, createMock, listAllocationsMock, listUsersMock } = vi.hoisted(() => ({
  listAssignmentsMock: vi.fn(),
  createMock: vi.fn(),
  listAllocationsMock: vi.fn(),
  listUsersMock: vi.fn(),
}));
vi.mock("@/api/teacherAssignments", () => ({
  teacherAssignmentsApi: {
    list: listAssignmentsMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/subjectAllocations", () => ({ listSubjectAllocations: listAllocationsMock }));
vi.mock("@/api/users", () => ({ listUsers: listUsersMock }));

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
    "teacher_assignments:create",
    "teacher_assignments:read",
    "teacher_assignments:update",
    "teacher_assignments:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const teacher: User = { ...baseUser, id: "teacher-1", username: "tsmith", full_name: "Terry Smith", roles: ["teacher"] };

const allocation: SubjectAllocation = {
  id: "alloc-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  section_id: "section-1",
  semester_id: "sem-1",
  academic_year_id: "year-1",
  teacher_user_id: "teacher-1",
  room_id: null,
  is_active: true,
};

const assignment: TeacherAssignment = {
  id: "assignment-1",
  institution_id: "inst-1",
  teacher_user_id: "teacher-1",
  subject_allocation_id: "alloc-1",
  assignment_role: "primary",
  assigned_from: "2026-06-01",
  assigned_to: null,
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
            <TeacherAssignmentsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("TeacherAssignmentsPage", () => {
  it("lists teacher assignments, resolving the teacher's name", async () => {
    listAssignmentsMock.mockResolvedValueOnce(page([assignment]));
    listAllocationsMock.mockResolvedValueOnce(page([allocation]));
    listUsersMock.mockResolvedValueOnce([teacher]);
    renderPage();
    expect(await screen.findByText("Terry Smith")).toBeInTheDocument();
    expect(screen.getByText("primary")).toBeInTheDocument();
  });

  it("creates a teacher assignment", async () => {
    listAssignmentsMock.mockResolvedValue(page([]));
    listAllocationsMock.mockResolvedValue(page([allocation]));
    listUsersMock.mockResolvedValue([teacher]);
    createMock.mockResolvedValueOnce(assignment);
    renderPage();

    await screen.findByText("No teacher assignments found.");
    await userEvent.click(screen.getByRole("button", { name: "New Assignment" }));
    await screen.findByText("Terry Smith", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Teacher/), "teacher-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Subject Allocation/), "alloc-1");
    await userEvent.type(screen.getByLabelText(/^Assigned From/), "2026-06-01");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ teacher_user_id: "teacher-1", subject_allocation_id: "alloc-1" }),
      ),
    );
  });
});
