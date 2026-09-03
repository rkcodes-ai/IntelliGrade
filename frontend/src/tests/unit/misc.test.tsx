import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import { Footer } from "@/components/layout/Footer";
import { ThemeProvider } from "@/context/ThemeProvider";
import { useHealthCheck } from "@/hooks/useHealthCheck";
import uiReducer from "@/store/slices/uiSlice";
import authReducer from "@/store/slices/authSlice";

describe("Footer", () => {
  it("renders the current year and product name", () => {
    render(<Footer />);
    expect(
      screen.getByText(new RegExp(`© ${new Date().getFullYear()} IntelliGrade`)),
    ).toBeInTheDocument();
  });
});

describe("ThemeProvider", () => {
  it("applies the 'dark' class to <html> when the ui theme is dark", () => {
    const store = configureStore({
      reducer: { ui: uiReducer, auth: authReducer },
      preloadedState: { ui: { theme: "dark" as const, sidebarCollapsed: false } },
    });

    render(
      <Provider store={store}>
        <ThemeProvider>
          <div>content</div>
        </ThemeProvider>
      </Provider>,
    );

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(window.localStorage.getItem("intelligrade-theme")).toBe("dark");
  });

  it("removes the 'dark' class when the ui theme is light", () => {
    document.documentElement.classList.add("dark");
    const store = configureStore({
      reducer: { ui: uiReducer, auth: authReducer },
      preloadedState: { ui: { theme: "light" as const, sidebarCollapsed: false } },
    });

    render(
      <Provider store={store}>
        <ThemeProvider>
          <div>content</div>
        </ThemeProvider>
      </Provider>,
    );

    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});

const { fetchHealthStatusMock } = vi.hoisted(() => ({ fetchHealthStatusMock: vi.fn() }));
vi.mock("@/api/health", () => ({ fetchHealthStatus: fetchHealthStatusMock }));

describe("useHealthCheck", () => {
  it("fetches and returns the backend health status", async () => {
    fetchHealthStatusMock.mockResolvedValueOnce({ status: "ok", environment: "test" });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useHealthCheck(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ status: "ok", environment: "test" });
  });
});
