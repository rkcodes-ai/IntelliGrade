import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { CoursesPage } from "@/pages/academic/CoursesPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Course, Program } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listCoursesMock, createMock, listProgramsMock } = vi.hoisted(() => ({
  listCoursesMock: vi.fn(),
  createMock: vi.fn(),
  listProgramsMock: vi.fn(),
}));
vi.mock("@/api/courses", () => ({
  coursesApi: {
    list: listCoursesMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/programs", () => ({ programsApi: { list: listProgramsMock } }));

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
  permissions: ["courses:create", "courses:read", "courses:update", "courses:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const program: Program = {
  id: "program-1",
  institution_id: "inst-1",
  department_id: "dept-1",
  name: "B.Tech",
  code: "BTECH",
  degree_type: "ug",
  duration_years: 4,
  total_semesters: 8,
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
            <CoursesPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("CoursesPage", () => {
  it("lists courses", async () => {
    listCoursesMock.mockResolvedValueOnce(page([course]));
    listProgramsMock.mockResolvedValueOnce(page([program]));
    renderPage();
    expect(await screen.findByText("Computer Science Engineering")).toBeInTheDocument();
    expect(await screen.findByText("B.Tech")).toBeInTheDocument();
  });

  it("creates a course", async () => {
    listCoursesMock.mockResolvedValue(page([]));
    listProgramsMock.mockResolvedValue(page([program]));
    createMock.mockResolvedValueOnce(course);
    renderPage();

    await screen.findByText("No courses found.");
    await userEvent.click(screen.getByRole("button", { name: "New Course" }));
    await screen.findByText("B.Tech", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Program/), "program-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Computer Science Engineering");
    await userEvent.type(screen.getByLabelText(/^Code/), "cse");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ program_id: "program-1", code: "CSE" }),
      ),
    );
  });
});
