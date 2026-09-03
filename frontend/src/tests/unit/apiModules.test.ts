import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import * as authApi from "@/api/auth";
import { apiClient } from "@/api/client";
import * as permissionsApi from "@/api/permissions";
import * as rolesApi from "@/api/roles";
import * as sessionsApi from "@/api/sessions";
import * as usersApi from "@/api/users";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

describe("api/auth", () => {
  it("login posts to /auth/login", async () => {
    mock
      .onPost("/auth/login")
      .reply(200, { access_token: "t", token_type: "bearer", expires_in: 1800 });
    const result = await authApi.login({ identifier: "a", password: "b", remember_me: false });
    expect(result.access_token).toBe("t");
  });

  it("logout posts to /auth/logout", async () => {
    mock.onPost("/auth/logout").reply(200, { message: "Logged out." });
    const result = await authApi.logout();
    expect(result.message).toBe("Logged out.");
  });

  it("forgotPassword posts to /auth/forgot-password", async () => {
    mock.onPost("/auth/forgot-password").reply(202, { message: "sent" });
    const result = await authApi.forgotPassword({ email: "a@example.com" });
    expect(result.message).toBe("sent");
  });

  it("resetPassword posts to /auth/reset-password", async () => {
    mock.onPost("/auth/reset-password").reply(200, { message: "reset" });
    const result = await authApi.resetPassword({ token: "t", new_password: "p" });
    expect(result.message).toBe("reset");
  });

  it("changePassword posts to /auth/change-password", async () => {
    mock.onPost("/auth/change-password").reply(200, { message: "changed" });
    const result = await authApi.changePassword({ current_password: "a", new_password: "b" });
    expect(result.message).toBe("changed");
  });
});

describe("api/users", () => {
  it("getMe fetches /users/me", async () => {
    mock.onGet("/users/me").reply(200, { username: "alice" });
    const result = await usersApi.getMe();
    expect(result.username).toBe("alice");
  });

  it("updateMe patches /users/me", async () => {
    mock.onPatch("/users/me").reply(200, { username: "alice", full_name: "Alice" });
    const result = await usersApi.updateMe({ full_name: "Alice" });
    expect(result.full_name).toBe("Alice");
  });

  it("listUsers fetches /users with params", async () => {
    mock.onGet("/users").reply((config) => {
      expect(config.params).toEqual({ limit: 10, offset: 0 });
      return [200, []];
    });
    await usersApi.listUsers({ limit: 10, offset: 0 });
  });

  it("getUser fetches /users/:id", async () => {
    mock.onGet("/users/user-1").reply(200, { id: "user-1" });
    const result = await usersApi.getUser("user-1");
    expect(result.id).toBe("user-1");
  });

  it("deactivateUser posts /users/:id/deactivate", async () => {
    mock.onPost("/users/user-1/deactivate").reply(200, { id: "user-1", is_active: false });
    const result = await usersApi.deactivateUser("user-1");
    expect(result.is_active).toBe(false);
  });

  it("activateUser posts /users/:id/activate", async () => {
    mock.onPost("/users/user-1/activate").reply(200, { id: "user-1", is_active: true });
    const result = await usersApi.activateUser("user-1");
    expect(result.is_active).toBe(true);
  });

  it("deleteUser deletes /users/:id", async () => {
    mock.onDelete("/users/user-1").reply(204);
    await expect(usersApi.deleteUser("user-1")).resolves.toBeUndefined();
  });
});

describe("api/roles", () => {
  it("getRoles fetches /roles", async () => {
    mock.onGet("/roles").reply(200, [{ name: "student" }]);
    const result = await rolesApi.getRoles();
    expect(result).toHaveLength(1);
  });
});

describe("api/permissions", () => {
  it("getPermissions fetches /permissions", async () => {
    mock.onGet("/permissions").reply(200, [{ code: "users:read" }]);
    const result = await permissionsApi.getPermissions();
    expect(result).toHaveLength(1);
  });
});

describe("api/sessions", () => {
  it("getSessions fetches /sessions", async () => {
    mock.onGet("/sessions").reply(200, [{ id: "session-1" }]);
    const result = await sessionsApi.getSessions();
    expect(result).toHaveLength(1);
  });

  it("revokeSession deletes /sessions/:id", async () => {
    mock.onDelete("/sessions/session-1").reply(204);
    await expect(sessionsApi.revokeSession("session-1")).resolves.toBeUndefined();
  });
});
