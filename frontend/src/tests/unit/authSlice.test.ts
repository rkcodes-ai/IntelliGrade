import { describe, expect, it } from "vitest";

import authReducer, {
  clearCredentials,
  setCredentials,
  updateUser,
} from "@/store/slices/authSlice";
import type { User } from "@/types/auth";

const mockUser: User = {
  id: "user-1",
  email: "alice@example.com",
  username: "alice",
  full_name: "Alice Example",
  phone: null,
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: false,
  roles: ["student"],
  permissions: ["sessions:read"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("authSlice", () => {
  const initialState = { user: null, accessToken: null, status: "idle" as const };

  it("starts unauthenticated with no user or token", () => {
    expect(initialState.status).toBe("idle");
  });

  it("setCredentials stores the user and token and marks authenticated", () => {
    const next = authReducer(
      initialState,
      setCredentials({ user: mockUser, accessToken: "token-abc" }),
    );
    expect(next.user).toEqual(mockUser);
    expect(next.accessToken).toBe("token-abc");
    expect(next.status).toBe("authenticated");
  });

  it("clearCredentials resets to unauthenticated", () => {
    const authenticated = authReducer(
      initialState,
      setCredentials({ user: mockUser, accessToken: "token-abc" }),
    );
    const next = authReducer(authenticated, clearCredentials());
    expect(next.user).toBeNull();
    expect(next.accessToken).toBeNull();
    expect(next.status).toBe("unauthenticated");
  });

  it("updateUser replaces the user without touching the token", () => {
    const authenticated = authReducer(
      initialState,
      setCredentials({ user: mockUser, accessToken: "token-abc" }),
    );
    const updated: User = { ...mockUser, full_name: "Alice Updated" };
    const next = authReducer(authenticated, updateUser(updated));
    expect(next.user?.full_name).toBe("Alice Updated");
    expect(next.accessToken).toBe("token-abc");
  });
});
