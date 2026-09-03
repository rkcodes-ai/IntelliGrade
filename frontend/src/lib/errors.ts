import { isAxiosError } from "axios";

import type { ApiErrorBody } from "@/types/auth";

/** Extracts the backend's `error.message` from an Axios error, with a generic fallback. */
export function extractErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (isAxiosError<ApiErrorBody>(error) && error.response?.data?.error?.message) {
    return error.response.data.error.message;
  }
  return fallback;
}
