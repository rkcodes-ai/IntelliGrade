import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "@/pages/ProfilePage";
import authReducer from "@/store/slices/authSlice";
import uiReducer from "@/store/slices/uiSlice";
import type { User } from "@/types/auth";

const { getMeMock, updateMeMock, changePasswordMock } = vi.hoisted(() => ({
  getMeMock: vi.fn(),
  updateMeMock: vi.fn(),
  changePasswordMock: vi.fn(),
}));
vi.mock("@/api/users", () => ({ getMe: getMeMock, updateMe: updateMeMock }));
vi.mock("@/api/auth", () => ({ changePassword: changePasswordMock }));

const mockUser: User = {
  id: "user-1",
  email: "alice@example.com",
  username: "alice",
  full_name: "Alice Example",
  phone: "555-1234",
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: false,
  roles: ["student"],
  permissions: [],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const store = configureStore({ reducer: { ui: uiReducer, auth: authReducer } });
  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <ProfilePage />
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ProfilePage", () => {
  it("loads and displays the current profile", async () => {
    getMeMock.mockResolvedValueOnce(mockUser);
    renderPage();

    expect(await screen.findByDisplayValue("Alice Example")).toBeInTheDocument();
    expect(screen.getByDisplayValue("555-1234")).toBeInTheDocument();
  });

  it("submits profile updates", async () => {
    getMeMock.mockResolvedValueOnce(mockUser);
    updateMeMock.mockResolvedValueOnce({ ...mockUser, full_name: "Alice Updated" });
    renderPage();

    const nameInput = await screen.findByDisplayValue("Alice Example");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Alice Updated");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByText("Profile updated.")).toBeInTheDocument());
    expect(updateMeMock).toHaveBeenCalled();
  });

  it("validates the change-password form", async () => {
    getMeMock.mockResolvedValueOnce(mockUser);
    renderPage();
    await screen.findByDisplayValue("Alice Example");

    await userEvent.type(screen.getByLabelText("New password"), "short");
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText("Enter your current password.")).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });
});
