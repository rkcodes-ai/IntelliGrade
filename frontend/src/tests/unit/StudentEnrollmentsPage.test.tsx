import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { StudentEnrollmentsPage } from "@/pages/academic/StudentEnrollmentsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type {
  AcademicStatus,
  AcademicYear,
  Batch,
  Course,
  Section,
  Semester,
  StudentEnrollment,
} from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  listEnrollmentsMock,
  createMock,
  listBatchesMock,
  listSectionsMock,
  listCoursesMock,
  listYearsMock,
  listSemestersMock,
  listStatusesMock,
  listUsersMock,
} = vi.hoisted(() => ({
  listEnrollmentsMock: vi.fn(),
  createMock: vi.fn(),
  listBatchesMock: vi.fn(),
  listSectionsMock: vi.fn(),
  listCoursesMock: vi.fn(),
  listYearsMock: vi.fn(),
  listSemestersMock: vi.fn(),
  listStatusesMock: vi.fn(),
  listUsersMock: vi.fn(),
}));
vi.mock("@/api/studentEnrollments", () => ({
  studentEnrollmentsApi: {
    list: listEnrollmentsMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/batches", () => ({ listBatches: listBatchesMock }));
vi.mock("@/api/sections", () => ({ sectionsApi: { list: listSectionsMock } }));
vi.mock("@/api/courses", () => ({ coursesApi: { list: listCoursesMock } }));
vi.mock("@/api/academicYears", () => ({ academicYearsApi: { list: listYearsMock } }));
vi.mock("@/api/semesters", () => ({ semestersApi: { list: listSemestersMock } }));
vi.mock("@/api/academicStatuses", () => ({ listAcademicStatuses: listStatusesMock }));
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
    "student_enrollments:create",
    "student_enrollments:read",
    "student_enrollments:update",
    "student_enrollments:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const student: User = { ...baseUser, id: "student-1", username: "jdoe", full_name: "Jane Doe", roles: ["student"] };

const batch: Batch = {
  id: "batch-1",
  institution_id: "inst-1",
  course_id: "course-1",
  name: "2026-2030",
  start_year: 2026,
  end_year: 2030,
  is_active: true,
};
const section: Section = {
  id: "section-1",
  institution_id: "inst-1",
  batch_id: "batch-1",
  name: "A",
  max_capacity: 60,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const course: Course = {
  id: "course-1",
  institution_id: "inst-1",
  program_id: "program-1",
  name: "Computer Science Engineering",
  code: "CSE",
  description: null,
  duration_years: 4,
  total_semesters: 8,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const year: AcademicYear = {
  id: "year-1",
  institution_id: "inst-1",
  year_label: "2026-2027",
  start_date: "2026-06-01",
  end_date: "2027-05-31",
  is_current: true,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const semester: Semester = {
  id: "sem-1",
  institution_id: "inst-1",
  academic_year_id: "year-1",
  name: "Semester 1",
  semester_number: 1,
  term_type: "odd",
  start_date: "2026-06-01",
  end_date: "2026-11-30",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const status: AcademicStatus = {
  id: "status-1",
  institution_id: "inst-1",
  code: "ACTIVE",
  name: "Active",
  is_terminal: false,
  is_active: true,
};

const enrollment: StudentEnrollment = {
  id: "enroll-1",
  institution_id: "inst-1",
  student_user_id: "student-1",
  batch_id: "batch-1",
  section_id: "section-1",
  course_id: "course-1",
  academic_year_id: "year-1",
  semester_id: "sem-1",
  academic_status_id: "status-1",
  roll_number: "R001",
  enrollment_date: "2026-06-05",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function mockAllSelectOptions() {
  listBatchesMock.mockResolvedValue(page([batch]));
  listSectionsMock.mockResolvedValue(page([section]));
  listCoursesMock.mockResolvedValue(page([course]));
  listYearsMock.mockResolvedValue(page([year]));
  listSemestersMock.mockResolvedValue(page([semester]));
  listStatusesMock.mockResolvedValue(page([status]));
  listUsersMock.mockResolvedValue([student]);
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
            <StudentEnrollmentsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("StudentEnrollmentsPage", () => {
  it("lists student enrollments, resolving student and status names", async () => {
    listEnrollmentsMock.mockResolvedValueOnce(page([enrollment]));
    mockAllSelectOptions();
    renderPage();
    expect(await screen.findByText("R001")).toBeInTheDocument();
    expect(await screen.findByText("Jane Doe")).toBeInTheDocument();
    expect(await screen.findByText("Active")).toBeInTheDocument();
  });

  it("creates a student enrollment by selecting every FK", async () => {
    listEnrollmentsMock.mockResolvedValue(page([]));
    mockAllSelectOptions();
    createMock.mockResolvedValueOnce(enrollment);
    renderPage();

    await screen.findByText("No student enrollments found.");
    await userEvent.click(screen.getByRole("button", { name: "New Enrollment" }));

    await screen.findByText("Jane Doe", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Student/), "student-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Course/), "course-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Batch/), "batch-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Section/), "section-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Academic Year/), "year-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Semester/), "sem-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Academic Status/), "status-1");
    await userEvent.type(screen.getByLabelText(/^Roll Number/), "R001");
    await userEvent.type(screen.getByLabelText(/^Enrollment Date/), "2026-06-05");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          student_user_id: "student-1",
          course_id: "course-1",
          batch_id: "batch-1",
          section_id: "section-1",
          academic_year_id: "year-1",
          semester_id: "sem-1",
          academic_status_id: "status-1",
          roll_number: "R001",
          enrollment_date: "2026-06-05",
        }),
      ),
    );
  });
});
