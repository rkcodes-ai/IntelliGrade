import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProcessingHistoryPage } from "@/pages/ocr/ProcessingHistoryPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { ProcessingHistory } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { listMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
}));
vi.mock("@/api/processingHistory", () => ({
  listProcessingHistory: listMock,
  getProcessingHistory: vi.fn(),
}));

const baseUser: User = {
  id: "user-1",
  email: "admin@example.com",
  username: "admin",
  full_name: "Admin",
  phone: null,
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: true,
  roles: ["institution_admin"],
  permissions: [],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const historyForScript1: ProcessingHistory = {
  id: "history-1",
  institution_id: "inst-1",
  answer_script_id: "script-1",
  stage: "ocr",
  from_status: "ocr_queued",
  to_status: "ocr_running",
  duration_ms: 1200,
  error_detail: null,
  triggered_by: "system",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page(items: ProcessingHistory[]): Page<ProcessingHistory> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage(scriptId = "script-1") {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: baseUser, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/dashboard/answer-scripts/${scriptId}/history`]}>
          <Routes>
            <Route
              path="/dashboard/answer-scripts/:scriptId/history"
              element={<ProcessingHistoryPage />}
            />
          </Routes>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ProcessingHistoryPage", () => {
  it("lists processing history filtered to the route's scriptId", async () => {
    listMock.mockResolvedValueOnce(page([historyForScript1]));
    renderPage("script-1");

    expect(await screen.findByText("ocr")).toBeInTheDocument();
    expect(screen.getByText("ocr_queued → ocr_running")).toBeInTheDocument();
    expect(screen.getByText("1200ms")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(
      expect.objectContaining({ answer_script_id: "script-1" }),
    );
  });

  it("navigates back when Back to script is clicked", async () => {
    listMock.mockResolvedValueOnce(page([historyForScript1]));
    renderPage("script-1");

    await screen.findByText("ocr");
    await userEvent.click(screen.getByRole("button", { name: "Back to script" }));
    expect(navigateMock).toHaveBeenCalledWith(-1);
  });

  it("shows an empty state when there is no history", async () => {
    listMock.mockResolvedValue(page([]));
    renderPage("script-2");

    expect(await screen.findByText("No processing history found.")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(
      expect.objectContaining({ answer_script_id: "script-2" }),
    );
  });
});
