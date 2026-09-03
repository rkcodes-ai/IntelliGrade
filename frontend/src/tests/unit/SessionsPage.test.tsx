import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { SessionsPage } from "@/pages/SessionsPage";
import { ToastProvider } from "@/context/ToastProvider";
import type { Session } from "@/types/auth";

const { getSessionsMock, revokeSessionMock } = vi.hoisted(() => ({
  getSessionsMock: vi.fn(),
  revokeSessionMock: vi.fn(),
}));
vi.mock("@/api/sessions", () => ({
  getSessions: getSessionsMock,
  revokeSession: revokeSessionMock,
}));

const sessions: Session[] = [
  {
    id: "session-1",
    ip_address: "127.0.0.1",
    user_agent: "Mozilla/5.0",
    device_label: "Chrome on Windows",
    is_active: true,
    last_active_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-02-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    is_current: true,
  },
  {
    id: "session-2",
    ip_address: "10.0.0.5",
    user_agent: "Mozilla/5.0",
    device_label: "Safari on macOS",
    is_active: true,
    last_active_at: "2026-01-02T00:00:00Z",
    expires_at: "2026-02-02T00:00:00Z",
    created_at: "2026-01-02T00:00:00Z",
    is_current: false,
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <SessionsPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SessionsPage", () => {
  it("lists sessions and marks the current one", async () => {
    getSessionsMock.mockResolvedValueOnce(sessions);
    renderPage();

    expect(await screen.findByText("Chrome on Windows")).toBeInTheDocument();
    expect(screen.getByText("Safari on macOS")).toBeInTheDocument();
    expect(screen.getByText("This device")).toBeInTheDocument();
  });

  it("shows an empty state when there are no sessions", async () => {
    getSessionsMock.mockResolvedValueOnce([]);
    renderPage();

    expect(await screen.findByText("No active sessions.")).toBeInTheDocument();
  });

  it("revokes a session when its Revoke button is clicked", async () => {
    getSessionsMock.mockResolvedValue(sessions);
    revokeSessionMock.mockResolvedValueOnce(undefined);
    renderPage();

    const revokeButtons = await screen.findAllByRole("button", { name: "Revoke" });
    await userEvent.click(revokeButtons[0]);

    // TanStack Query v5 calls `mutationFn` with a second (internal context)
    // argument beyond the variable we pass to `.mutate()` — assert on the
    // first argument specifically rather than the exact call signature.
    await waitFor(() => expect(revokeSessionMock.mock.calls[0]?.[0]).toBe("session-1"));
  });
});
