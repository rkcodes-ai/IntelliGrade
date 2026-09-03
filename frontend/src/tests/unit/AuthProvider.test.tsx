import { configureStore } from "@reduxjs/toolkit";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/context/AuthProvider";
import authReducer from "@/store/slices/authSlice";
import uiReducer from "@/store/slices/uiSlice";
import type { User } from "@/types/auth";

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }));
vi.mock("@/api/client", () => ({ apiClient: { post: postMock } }));

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

function renderWithProvider() {
  const store = configureStore({ reducer: { ui: uiReducer, auth: authReducer } });
  render(
    <Provider store={store}>
      <AuthProvider>
        <div>App content</div>
      </AuthProvider>
    </Provider>,
  );
  return store;
}

describe("AuthProvider", () => {
  it("restores the session when a valid refresh cookie exists", async () => {
    postMock.mockResolvedValueOnce({
      data: {
        access_token: "restored-token",
        token_type: "bearer",
        expires_in: 1800,
        user: mockUser,
      },
    });

    const store = renderWithProvider();

    expect(await screen.findByText("App content")).toBeInTheDocument();
    expect(store.getState().auth.status).toBe("authenticated");
    expect(store.getState().auth.accessToken).toBe("restored-token");
  });

  it("marks unauthenticated (without erroring) when there is no valid session", async () => {
    postMock.mockRejectedValueOnce(new Error("No refresh token presented."));

    const store = renderWithProvider();

    expect(await screen.findByText("App content")).toBeInTheDocument();
    expect(store.getState().auth.status).toBe("unauthenticated");
  });

  it("shows a loading screen while the bootstrap check is in flight", () => {
    postMock.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProvider();

    expect(screen.getByText("Loading your session…")).toBeInTheDocument();
  });
});
