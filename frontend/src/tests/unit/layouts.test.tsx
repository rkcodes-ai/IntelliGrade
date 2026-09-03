import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { ToastProvider } from "@/context/ToastProvider";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import uiReducer from "@/store/slices/uiSlice";

vi.mock("@/api/institutions", () => ({ listMyInstitutions: vi.fn().mockResolvedValue([]) }));

function renderWithStore(ui: React.ReactElement, initialEntries: string[]) {
  const store = configureStore({
    reducer: { ui: uiReducer, auth: authReducer, institution: institutionReducer },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <ToastProvider>
          <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
        </ToastProvider>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AuthLayout", () => {
  it("renders the IntelliGrade heading and the nested route's content", () => {
    renderWithStore(
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<div>Login form</div>} />
        </Route>
      </Routes>,
      ["/login"],
    );
    expect(screen.getByText("IntelliGrade")).toBeInTheDocument();
    expect(screen.getByText("Login form")).toBeInTheDocument();
  });
});

describe("DashboardLayout", () => {
  it("renders the topbar, sidebar, footer, and nested route content", () => {
    renderWithStore(
      <Routes>
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<div>Dashboard body</div>} />
        </Route>
      </Routes>,
      ["/dashboard"],
    );
    expect(screen.getByText("Dashboard body")).toBeInTheDocument();
    expect(screen.getByText("Skip to main content")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
  });
});
