/**
 * Shared Axios instance for all backend requests.
 *
 * Request interceptor: attaches the access token from the Redux auth slice.
 * Response interceptor: on a 401 (and the failing request wasn't already a
 * retry, wasn't the refresh call itself, and wasn't a login attempt),
 * transparently calls `/auth/refresh` (which reads the httpOnly refresh
 * cookie the browser already sends — see `withCredentials: true` below),
 * updates the store with the new access token, and retries the original
 * request once. If refresh itself fails, credentials are cleared and the
 * user is sent to `/login` — see `docs/authentication-guide.md`.
 *
 * Imports `store` directly (not through a hook, since this runs outside
 * React) — safe because `store/index.ts` and `authSlice.ts` have no
 * dependency on this module or anything in `api/`, so there's no import
 * cycle despite the two-way relationship at the feature level.
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { env } from "@/config/env";
import { clearCredentials, setCredentials } from "@/store/slices/authSlice";
import { store } from "@/store";
import type { ApiErrorBody, TokenResponse } from "@/types/auth";

declare module "axios" {
  interface InternalAxiosRequestConfig {
    _retry?: boolean;
  }
}

const REFRESH_URL = "/auth/refresh";
const NO_REFRESH_RETRY_PATHS = ["/auth/refresh", "/auth/login"];

export const apiClient = axios.create({
  baseURL: env.VITE_API_BASE_URL,
  timeout: 15_000,
  withCredentials: true, // send/receive the httpOnly refresh-token cookie
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = store.getState().auth.accessToken;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  // Every Academic Domain (Module 03) endpoint requires this header to
  // resolve its tenant — see backend `app/core/tenancy.py`. Institution
  // endpoints themselves don't need it (Institution is the tenant root),
  // but sending it unconditionally is harmless since they ignore it.
  const institutionId = store.getState().institution.currentInstitutionId;
  if (institutionId) {
    config.headers.set("X-Institution-Id", institutionId);
  }
  return config;
});

// Shared in-flight refresh promise so concurrent 401s trigger exactly one
// refresh call instead of a stampede.
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  refreshPromise ??= apiClient
    .post<TokenResponse>(REFRESH_URL)
    .then(({ data }) => {
      store.dispatch(setCredentials({ user: data.user, accessToken: data.access_token }));
      return data.access_token;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const config = error.config;
    const status = error.response?.status;
    const url = config?.url ?? "";
    const isExemptPath = NO_REFRESH_RETRY_PATHS.some((path) => url.includes(path));

    if (status === 401 && config && !config._retry && !isExemptPath) {
      config._retry = true;
      try {
        const newToken = await refreshAccessToken();
        config.headers.set("Authorization", `Bearer ${newToken}`);
        return apiClient(config);
      } catch (refreshError) {
        store.dispatch(clearCredentials());
        if (typeof window !== "undefined") {
          window.location.assign("/login");
        }
        return Promise.reject(refreshError);
      }
    }

    if (import.meta.env.DEV) {
      console.error("[API Error]", error.response?.data ?? error.message);
    }
    return Promise.reject(error);
  },
);
