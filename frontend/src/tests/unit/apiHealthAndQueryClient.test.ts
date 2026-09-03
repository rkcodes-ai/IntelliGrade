import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { fetchHealthStatus } from "@/api/health";
import { apiClient } from "@/api/client";
import { queryClient } from "@/api/queryClient";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

describe("api/health", () => {
  it("fetches /health from the API origin", async () => {
    mock.onGet("/health").reply(200, { status: "ok", environment: "test" });
    const result = await fetchHealthStatus();
    expect(result).toEqual({ status: "ok", environment: "test" });
  });
});

describe("api/queryClient", () => {
  it("is configured with sane defaults for retries and refetch behavior", () => {
    const defaults = queryClient.getDefaultOptions();
    expect(defaults.queries?.retry).toBe(1);
    expect(defaults.queries?.staleTime).toBe(30_000);
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
    expect(defaults.mutations?.retry).toBe(0);
  });
});
