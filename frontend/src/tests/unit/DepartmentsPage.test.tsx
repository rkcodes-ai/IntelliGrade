import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { DepartmentsPage } from "@/pages/academic/DepartmentsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Campus, Department } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listDepartmentsMock, createMock, listCampusesMock } = vi.hoisted(() => ({
  listDepartmentsMock: vi.fn(),
  createMock: vi.fn(),
  listCampusesMock: vi.fn(),
}));
vi.mock("@/api/departments", () => ({
  departmentsApi: {
    list: listDepartmentsMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/campuses", () => ({
  campusesApi: { list: listCampusesMock },
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
  permissions: ["departments:create", "departments:read", "departments:update", "departments:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const campus: Campus = {
  id: "campus-1",
  institution_id: "inst-1",
  name: "Main Campus",
  code: "MAIN",
  address: null,
  city: null,
  state: null,
  country: null,
  is_main_campus: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
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
            <DepartmentsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("DepartmentsPage", () => {
  it("lists departments, resolving the campus name from the select-options query", async () => {
    listDepartmentsMock.mockResolvedValueOnce(page([department]));
    listCampusesMock.mockResolvedValueOnce(page([campus]));
    renderPage();

    expect(await screen.findByText("Computer Science")).toBeInTheDocument();
    expect(await screen.findByText("Main Campus")).toBeInTheDocument();
  });

  it("creates a department by selecting a campus from the dropdown", async () => {
    listDepartmentsMock.mockResolvedValue(page([]));
    listCampusesMock.mockResolvedValue(page([campus]));
    createMock.mockResolvedValueOnce(department);
    renderPage();

    await screen.findByText("No departments found.");
    await userEvent.click(screen.getByRole("button", { name: "New Department" }));

    await screen.findByText("Main Campus", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Campus/), "campus-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Computer Science");
    await userEvent.type(screen.getByLabelText(/^Code/), "cs");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ campus_id: "campus-1", name: "Computer Science", code: "CS" }),
      ),
    );
  });
});
