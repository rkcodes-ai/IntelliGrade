import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { ProgramsPage } from "@/pages/academic/ProgramsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Department, Program } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listProgramsMock, createMock, listDepartmentsMock } = vi.hoisted(() => ({
  listProgramsMock: vi.fn(),
  createMock: vi.fn(),
  listDepartmentsMock: vi.fn(),
}));
vi.mock("@/api/programs", () => ({
  programsApi: {
    list: listProgramsMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/departments", () => ({ departmentsApi: { list: listDepartmentsMock } }));

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
  permissions: ["programs:create", "programs:read", "programs:update", "programs:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const department: Department = {
  id: "dept-1",
  institution_id: "inst-1",
  campus_id: "campus-1",
  name: "Computer Science",
  code: "CS",
  description: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
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
            <ProgramsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ProgramsPage", () => {
  it("lists programs", async () => {
    listProgramsMock.mockResolvedValueOnce(page([program]));
    listDepartmentsMock.mockResolvedValueOnce(page([department]));
    renderPage();
    expect(await screen.findByText("B.Tech")).toBeInTheDocument();
    expect(await screen.findByText("Computer Science")).toBeInTheDocument();
  });

  it("creates a program", async () => {
    listProgramsMock.mockResolvedValue(page([]));
    listDepartmentsMock.mockResolvedValue(page([department]));
    createMock.mockResolvedValueOnce(program);
    renderPage();

    await screen.findByText("No programs found.");
    await userEvent.click(screen.getByRole("button", { name: "New Program" }));
    await screen.findByText("Computer Science", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Department/), "dept-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "B.Tech");
    await userEvent.type(screen.getByLabelText(/^Code/), "btech");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ department_id: "dept-1", name: "B.Tech", code: "BTECH" }),
      ),
    );
  });
});
