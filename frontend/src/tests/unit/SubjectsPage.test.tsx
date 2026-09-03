import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { SubjectsPage } from "@/pages/academic/SubjectsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Course, Subject, SubjectCategory } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listSubjectsMock, createMock, listCoursesMock, listCategoriesMock } = vi.hoisted(() => ({
  listSubjectsMock: vi.fn(),
  createMock: vi.fn(),
  listCoursesMock: vi.fn(),
  listCategoriesMock: vi.fn(),
}));
vi.mock("@/api/subjects", () => ({
  subjectsApi: {
    list: listSubjectsMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/courses", () => ({ coursesApi: { list: listCoursesMock } }));
vi.mock("@/api/subjectCategories", () => ({ listSubjectCategories: listCategoriesMock }));

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
  permissions: ["subjects:create", "subjects:read", "subjects:update", "subjects:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
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

const category: SubjectCategory = {
  id: "cat-1",
  institution_id: "inst-1",
  code: "CORE",
  name: "Core",
  is_active: true,
};

const subject: Subject = {
  id: "subject-1",
  institution_id: "inst-1",
  course_id: "course-1",
  subject_category_id: "cat-1",
  code: "CS101",
  name: "Intro to Programming",
  credits: "4.00",
  semester_number: 1,
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
            <SubjectsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("SubjectsPage", () => {
  it("lists subjects", async () => {
    listSubjectsMock.mockResolvedValueOnce(page([subject]));
    listCoursesMock.mockResolvedValueOnce(page([course]));
    listCategoriesMock.mockResolvedValueOnce(page([category]));
    renderPage();
    expect(await screen.findByText("Intro to Programming")).toBeInTheDocument();
    expect(await screen.findByText("Computer Science Engineering")).toBeInTheDocument();
    expect(await screen.findByText("Core")).toBeInTheDocument();
  });

  it("creates a subject", async () => {
    listSubjectsMock.mockResolvedValue(page([]));
    listCoursesMock.mockResolvedValue(page([course]));
    listCategoriesMock.mockResolvedValue(page([category]));
    createMock.mockResolvedValueOnce(subject);
    renderPage();

    await screen.findByText("No subjects found.");
    await userEvent.click(screen.getByRole("button", { name: "New Subject" }));
    await screen.findByText("Computer Science Engineering", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Course/), "course-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Category/), "cat-1");
    await userEvent.type(screen.getByLabelText(/^Code/), "cs101");
    await userEvent.type(screen.getByLabelText(/^Name/), "Intro to Programming");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ course_id: "course-1", subject_category_id: "cat-1", code: "CS101" }),
      ),
    );
  });
});
