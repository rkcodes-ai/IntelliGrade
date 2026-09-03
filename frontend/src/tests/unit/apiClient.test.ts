/**
 * Tests the axios interceptor logic in `api/client.ts`: token attachment,
 * transparent refresh-on-401 with retry, concurrent-401 de-duplication,
 * and logout-on-refresh-failure. Uses `axios-mock-adapter` so the real
 * interceptors run against a mocked HTTP layer rather than a real backend.
 */
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { store } from "@/store";
import { clearCredentials, setCredentials } from "@/store/slices/authSlice";
import type { User } from "@/types/auth";

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
  roles: ["student"],
  permissions: [],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
  store.dispatch(clearCredentials());
});

afterEach(() => {
  mock.restore();
});

describe("apiClient request interceptor", () => {
  it("attaches the Authorization header when a token is present", async () => {
    store.dispatch(setCredentials({ user: mockUser, accessToken: "my-token" }));
    mock.onGet("/protected").reply((config) => {
      expect(config.headers?.Authorization).toBe("Bearer my-token");
      return [200, { ok: true }];
    });

    const response = await apiClient.get("/protected");
    expect(response.status).toBe(200);
  });

  it("sends no Authorization header when there is no token", async () => {
    mock.onGet("/public").reply((config) => {
      expect(config.headers?.Authorization).toBeUndefined();
      return [200, { ok: true }];
    });

    await apiClient.get("/public");
  });
});

describe("apiClient response interceptor: 401 refresh flow", () => {
  it("refreshes the token and retries the original request once on 401", async () => {
    store.dispatch(setCredentials({ user: mockUser, accessToken: "expired-token" }));

    let protectedCallCount = 0;
    mock.onGet("/protected").reply((config) => {
      protectedCallCount += 1;
      if (config.headers?.Authorization === "Bearer expired-token") {
        return [401, { error: { code: "unauthorized", message: "Access token has expired." } }];
      }
      return [200, { ok: true }];
    });
    mock.onPost("/auth/refresh").reply(200, {
      access_token: "fresh-token",
      token_type: "bearer",
      expires_in: 1800,
      user: mockUser,
    });

    const response = await apiClient.get("/protected");

    expect(response.status).toBe(200);
    expect(protectedCallCount).toBe(2); // original (401) + retry (200)
    expect(store.getState().auth.accessToken).toBe("fresh-token");
  });

  it("clears credentials and does not retry when refresh itself fails", async () => {
    store.dispatch(setCredentials({ user: mockUser, accessToken: "expired-token" }));
    mock.onGet("/protected").reply(401, { error: { code: "unauthorized", message: "Expired." } });
    mock
      .onPost("/auth/refresh")
      .reply(401, { error: { code: "unauthorized", message: "No refresh token presented." } });

    // jsdom's `window.location.assign` isn't implemented; stub it so the
    // interceptor's post-failure redirect doesn't throw during the test.
    const assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...window.location, assign: assignSpy },
      writable: true,
    });

    await expect(apiClient.get("/protected")).rejects.toBeTruthy();

    expect(store.getState().auth.status).toBe("unauthenticated");
    expect(store.getState().auth.accessToken).toBeNull();
    expect(assignSpy).toHaveBeenCalledWith("/login");
  });

  it("does not attempt to refresh on a 401 from the login endpoint itself", async () => {
    mock
      .onPost("/auth/login")
      .reply(401, { error: { code: "unauthorized", message: "Bad creds." } });
    let refreshCalled = false;
    mock.onPost("/auth/refresh").reply(() => {
      refreshCalled = true;
      return [200, {}];
    });

    await expect(
      apiClient.post("/auth/login", { identifier: "x", password: "y" }),
    ).rejects.toBeTruthy();

    expect(refreshCalled).toBe(false);
  });

  it("de-duplicates concurrent refresh calls into a single request", async () => {
    store.dispatch(setCredentials({ user: mockUser, accessToken: "expired-token" }));

    mock.onGet(/\/protected-\d/).reply((config) => {
      if (config.headers?.Authorization === "Bearer expired-token") {
        return [401, { error: { code: "unauthorized", message: "Expired." } }];
      }
      return [200, { ok: true }];
    });

    let refreshCallCount = 0;
    mock.onPost("/auth/refresh").reply(() => {
      refreshCallCount += 1;
      return [
        200,
        { access_token: "fresh-token", token_type: "bearer", expires_in: 1800, user: mockUser },
      ];
    });

    const [r1, r2, r3] = await Promise.all([
      apiClient.get("/protected-1"),
      apiClient.get("/protected-2"),
      apiClient.get("/protected-3"),
    ]);

    expect([r1.status, r2.status, r3.status]).toEqual([200, 200, 200]);
    expect(refreshCallCount).toBe(1);
  });
});
