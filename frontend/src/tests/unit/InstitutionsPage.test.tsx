import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { InstitutionsPage } from "@/pages/academic/InstitutionsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Institution } from "@/types/academic";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, createMock, updateMock, removeMock, restoreMock, listDeletedMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  restoreMock: vi.fn(),
  listDeletedMock: vi.fn(),
}));
vi.mock("@/api/institutions", () => ({
  institutionsApi: {
    list: listMock,
    listDeleted: listDeletedMock,
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
    restore: restoreMock,
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
  roles: ["super_admin"],
  permissions: ["institutions:create", "institutions:read", "institutions:update", "institutions:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const institution: Institution = {
  id: "inst-1",
  name: "Acme University",
  code: "ACME",
  institution_type: "university",
  address: null,
  city: "Springfield",
  state: null,
  country: null,
  postal_code: null,
  phone: null,
  email: null,
  website: null,
  established_year: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page(items: Institution[]): Page<Institution> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage() {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: baseUser, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: null },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter>
          <ToastProvider>
            <InstitutionsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("InstitutionsPage", () => {
  it("lists institutions", async () => {
    listMock.mockResolvedValueOnce(page([institution]));
    renderPage();
    expect(await screen.findByText("Acme University")).toBeInTheDocument();
    expect(screen.getByText("ACME")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    listMock.mockResolvedValueOnce(page([]));
    renderPage();
    expect(await screen.findByText("No institutions found.")).toBeInTheDocument();
  });

  it("creates a new institution via the dialog", async () => {
    listMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(institution);
    renderPage();

    await screen.findByText("No institutions found.");
    await userEvent.click(screen.getByRole("button", { name: "New Institution" }));
    await userEvent.type(screen.getByLabelText(/^Name/), "Acme University");
    await userEvent.type(screen.getByLabelText(/^Code/), "acme");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Acme University", code: "ACME" }),
      ),
    );
  });

  it("edits an existing institution", async () => {
    listMock.mockResolvedValue(page([institution]));
    updateMock.mockResolvedValueOnce({ ...institution, city: "Shelbyville" });
    renderPage();

    await screen.findByText("Acme University");
    await userEvent.click(screen.getByRole("button", { name: "Edit Acme University" }));
    const cityInput = screen.getByLabelText("City");
    await userEvent.clear(cityInput);
    await userEvent.type(cityInput, "Shelbyville");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        "inst-1",
        expect.objectContaining({ city: "Shelbyville" }),
      ),
    );
  });

  it("deletes an institution after confirmation", async () => {
    listMock.mockResolvedValue(page([institution]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Acme University");
    await userEvent.click(screen.getByRole("button", { name: "Delete Acme University" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("inst-1"));
  });
});
