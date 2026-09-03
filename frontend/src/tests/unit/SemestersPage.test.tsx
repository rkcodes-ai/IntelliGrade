import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { SemestersPage } from "@/pages/academic/SemestersPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AcademicYear, Semester } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listSemestersMock, createMock, listYearsMock } = vi.hoisted(() => ({
  listSemestersMock: vi.fn(),
  createMock: vi.fn(),
  listYearsMock: vi.fn(),
}));
vi.mock("@/api/semesters", () => ({
  semestersApi: {
    list: listSemestersMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/academicYears", () => ({ academicYearsApi: { list: listYearsMock } }));

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
  permissions: ["semesters:create", "semesters:read", "semesters:update", "semesters:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
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
            <SemestersPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("SemestersPage", () => {
  it("lists semesters", async () => {
    listSemestersMock.mockResolvedValueOnce(page([semester]));
    listYearsMock.mockResolvedValueOnce(page([year]));
    renderPage();
    expect(await screen.findByText("Semester 1")).toBeInTheDocument();
    expect(await screen.findByText("2026-2027")).toBeInTheDocument();
  });

  it("creates a semester", async () => {
    listSemestersMock.mockResolvedValue(page([]));
    listYearsMock.mockResolvedValue(page([year]));
    createMock.mockResolvedValueOnce(semester);
    renderPage();

    await screen.findByText("No semesters found.");
    await userEvent.click(screen.getByRole("button", { name: "New Semester" }));
    await screen.findByText("2026-2027", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Academic Year/), "year-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Semester 1");
    await userEvent.type(screen.getByLabelText(/^Start Date/), "2026-06-01");
    await userEvent.type(screen.getByLabelText(/^End Date/), "2026-11-30");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ academic_year_id: "year-1", name: "Semester 1" }),
      ),
    );
  });
});
