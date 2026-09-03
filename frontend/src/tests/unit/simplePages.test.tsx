import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LandingPage } from "@/pages/LandingPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { UnauthorizedPage } from "@/pages/UnauthorizedPage";

const { fetchHealthStatusMock } = vi.hoisted(() => ({ fetchHealthStatusMock: vi.fn() }));
vi.mock("@/api/health", () => ({ fetchHealthStatus: fetchHealthStatusMock }));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LandingPage", () => {
  it("shows a sign-in link and reports live backend connectivity", async () => {
    fetchHealthStatusMock.mockResolvedValueOnce({ status: "ok", environment: "test" });
    renderWithProviders(<LandingPage />);

    expect(screen.getByRole("link", { name: "Sign in to Platform" })).toHaveAttribute("href", "/login");
    expect(await screen.findByText(/Connected · environment: test/)).toBeInTheDocument();
  });
});

describe("UnauthorizedPage", () => {
  it("renders a 403 message with a link back to the dashboard", () => {
    renderWithProviders(<UnauthorizedPage />);
    expect(screen.getByText("403 — Access denied")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to dashboard" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});

describe("NotFoundPage", () => {
  it("renders a 404 message with a link home", () => {
    renderWithProviders(<NotFoundPage />);
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go home" })).toHaveAttribute("href", "/");
  });
});

// DashboardHomePage now needs a Redux store (auth/institution state) and
// several mocked API modules — see `DashboardHomePage.test.tsx`.
