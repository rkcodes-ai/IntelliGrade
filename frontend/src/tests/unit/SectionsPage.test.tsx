import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { SectionsPage } from "@/pages/academic/SectionsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Batch, Section } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listSectionsMock, createMock, listBatchesMock } = vi.hoisted(() => ({
  listSectionsMock: vi.fn(),
  createMock: vi.fn(),
  listBatchesMock: vi.fn(),
}));
vi.mock("@/api/sections", () => ({
  sectionsApi: {
    list: listSectionsMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/batches", () => ({ listBatches: listBatchesMock }));

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
  permissions: ["sections:create", "sections:read", "sections:update", "sections:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

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
            <SectionsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("SectionsPage", () => {
  it("lists sections", async () => {
    listSectionsMock.mockResolvedValueOnce(page([section]));
    listBatchesMock.mockResolvedValueOnce(page([batch]));
    renderPage();
    expect(await screen.findByText("A")).toBeInTheDocument();
    expect(await screen.findByText("2026-2030")).toBeInTheDocument();
  });

  it("creates a section", async () => {
    listSectionsMock.mockResolvedValue(page([]));
    listBatchesMock.mockResolvedValue(page([batch]));
    createMock.mockResolvedValueOnce(section);
    renderPage();

    await screen.findByText("No sections found.");
    await userEvent.click(screen.getByRole("button", { name: "New Section" }));
    await screen.findByText("2026-2030", { selector: "option" });
    await userEvent.selectOptions(screen.getByLabelText(/^Batch/), "batch-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "A");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ batch_id: "batch-1", name: "A" })),
    );
  });
});
