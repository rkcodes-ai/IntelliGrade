import { configureStore } from "@reduxjs/toolkit";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PermissionGuard } from "@/routes/guards/PermissionGuard";
import { ProtectedRoute } from "@/routes/guards/ProtectedRoute";
import { RoleGuard } from "@/routes/guards/RoleGuard";
import authReducer from "@/store/slices/authSlice";
import uiReducer from "@/store/slices/uiSlice";
import type { User } from "@/types/auth";

const baseUser: User = {
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
  roles: ["teacher"],
  permissions: ["users:read"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

interface AuthState {
  user: User | null;
  accessToken: string | null;
  status: "idle" | "authenticated" | "unauthenticated";
}

// `MemoryRouter` + `Routes`/`Route` (the declarative API) is used here
// instead of `createMemoryRouter` + `RouterProvider` (the data-router API
// the app itself uses in `routes/index.tsx`): the data router's internal
// navigation goes through the Fetch API's `Request`/`AbortSignal`, which
// has a known incompatibility with jsdom's polyfills under Vitest. The
// guard components themselves don't care which router flavor renders
// them, so the declarative API is a faithful, jsdom-safe stand-in for
// testing purposes.
function renderWithGuard(guardElement: React.ReactElement, authState: AuthState) {
  const store = configureStore({
    reducer: { ui: uiReducer, auth: authReducer },
    preloadedState: { auth: authState, ui: { theme: "light" as const, sidebarCollapsed: false } },
  });

  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={["/protected"]}>
        <Routes>
          <Route element={guardElement}>
            <Route path="/protected" element={<div>Protected content</div>} />
          </Route>
          <Route path="/login" element={<div>Login page</div>} />
          <Route path="/unauthorized" element={<div>Unauthorized page</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

describe("ProtectedRoute", () => {
  it("renders the protected content when authenticated", () => {
    renderWithGuard(<ProtectedRoute />, {
      user: baseUser,
      accessToken: "token",
      status: "authenticated",
    });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("redirects to /login when unauthenticated", () => {
    renderWithGuard(<ProtectedRoute />, {
      user: null,
      accessToken: null,
      status: "unauthenticated",
    });
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });
});

describe("RoleGuard", () => {
  it("renders content when the user has an allowed role", () => {
    renderWithGuard(<RoleGuard allowedRoles={["teacher", "super_admin"]} />, {
      user: baseUser,
      accessToken: "token",
      status: "authenticated",
    });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("redirects to /unauthorized when the user lacks an allowed role", () => {
    renderWithGuard(<RoleGuard allowedRoles={["super_admin"]} />, {
      user: baseUser,
      accessToken: "token",
      status: "authenticated",
    });
    expect(screen.getByText("Unauthorized page")).toBeInTheDocument();
  });

  it("redirects to /unauthorized when there is no user at all", () => {
    renderWithGuard(<RoleGuard allowedRoles={["teacher"]} />, {
      user: null,
      accessToken: null,
      status: "unauthenticated",
    });
    expect(screen.getByText("Unauthorized page")).toBeInTheDocument();
  });
});

describe("PermissionGuard", () => {
  it("renders content when the user has all required permissions", () => {
    renderWithGuard(<PermissionGuard requiredPermissions={["users:read"]} />, {
      user: baseUser,
      accessToken: "token",
      status: "authenticated",
    });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("redirects to /unauthorized when missing one of several required permissions", () => {
    renderWithGuard(<PermissionGuard requiredPermissions={["users:read", "users:delete"]} />, {
      user: baseUser,
      accessToken: "token",
      status: "authenticated",
    });
    expect(screen.getByText("Unauthorized page")).toBeInTheDocument();
  });
});
