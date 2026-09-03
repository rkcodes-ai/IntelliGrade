import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { CampusesPage } from "@/pages/academic/CampusesPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Campus } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, createMock, updateMock, removeMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
}));
vi.mock("@/api/campuses", () => ({
  campusesApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
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
  permissions: ["campuses:create", "campuses:read", "campuses:update", "campuses:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const campus: Campus = {
  id: "campus-1",
  institution_id: "inst-1",
  name: "Main Campus",
  code: "MAIN",
  address: null,
  city: "Springfield",
  state: null,
  country: null,
  is_main_campus: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page(items: Campus[]): Page<Campus> {
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
            <CampusesPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("CampusesPage", () => {
  it("lists campuses for the current institution", async () => {
    listMock.mockResolvedValueOnce(page([campus]));
    renderPage();
    expect(await screen.findByText("Main Campus")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument(); // is_main_campus column
  });

  it("creates a campus", async () => {
    listMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(campus);
    renderPage();

    await screen.findByText("No campuses found.");
    await userEvent.click(screen.getByRole("button", { name: "New Campus" }));
    await userEvent.type(screen.getByLabelText(/^Name/), "Main Campus");
    await userEvent.type(screen.getByLabelText(/^Code/), "main");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ name: "Main Campus", code: "MAIN" })),
    );
  });

  it("deletes a campus after confirmation", async () => {
    listMock.mockResolvedValue(page([campus]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Main Campus");
    await userEvent.click(screen.getByRole("button", { name: "Delete Main Campus" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("campus-1"));
  });
});
