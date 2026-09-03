/**
 * Example API module wired to the backend's unversioned health endpoints.
 * Serves as the reference pattern future domain API modules should follow.
 */
import { apiClient } from "@/api/client";
import { env } from "@/config/env";
import type { HealthStatus } from "@/types";

// Health endpoints live unversioned at the API origin (see docs/architecture.md),
// not under /api/v1 — derive the origin from the validated base URL rather
// than string-manipulating the /api/v1 suffix.
const HEALTH_BASE_URL = new URL(env.VITE_API_BASE_URL).origin;

export async function fetchHealthStatus(): Promise<HealthStatus> {
  const { data } = await apiClient.get<HealthStatus>("/health", { baseURL: HEALTH_BASE_URL });
  return data;
}
