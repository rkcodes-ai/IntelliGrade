import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Topbar } from "@/components/layout/Topbar";
import { ToastProvider } from "@/context/ToastProvider";
import authReducer, { setCredentials } from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import uiReducer from "@/store/slices/uiSlice";
import type { User } from "@/types/auth";

const { logoutMock, listMyInstitutionsMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  listMyInstitutionsMock: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/api/auth", () => ({ logout: logoutMock }));
vi.mock("@/api/institutions", () => ({ listMyInstitutions: listMyInstitutionsMock }));

const mockUser: User = {
  id: "user-1",
  email: "alice@example.com",
  username: "alice",
  full_name: "Alice",
  phone: null,
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: false,
  roles: [],
  permissions: [],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function renderTopbar() {
  const store = configureStore({
    reducer: { ui: uiReducer, auth: authReducer, institution: institutionReducer },
  });
  store.dispatch(setCredentials({ user: mockUser, accessToken: "token" }));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard" element={<Topbar />} />
              <Route path="/login" element={<div>Login page</div>} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
  return store;
}

describe("Topbar", () => {
  it("shows the current user's username", () => {
    renderTopbar();
    expect(screen.getByText("alice")).toBeInTheDocument();
  });

  it("signs out and redirects to /login when the sign-out button is clicked", async () => {
    logoutMock.mockResolvedValueOnce({ message: "Logged out." });
    const store = renderTopbar();

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(screen.getByText("Login page")).toBeInTheDocument());
    expect(store.getState().auth.status).toBe("unauthenticated");
  });

  it("still clears local credentials and redirects even if the server logout call fails", async () => {
    logoutMock.mockRejectedValueOnce(new Error("network error"));
    const store = renderTopbar();

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(screen.getByText("Login page")).toBeInTheDocument());
    expect(store.getState().auth.status).toBe("unauthenticated");
  });
});
