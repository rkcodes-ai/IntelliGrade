import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AIProviderManagementPage } from "@/pages/ocr/AIProviderManagementPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AIProvider } from "@/types/officialExam";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, updateMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  updateMock: vi.fn(),
}));
vi.mock("@/api/aiProviders", () => ({
  listAIProviders: listMock,
  getAIProvider: vi.fn(),
  updateAIProvider: updateMock,
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
  roles: ["super_admin"],
  permissions: ["ai_providers:update"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const readOnlyUser: User = { ...baseUser, id: "user-2", permissions: [] };

function baseProvider(overrides: Partial<AIProvider> = {}): AIProvider {
  return {
    id: "provider-1",
    code: "openai",
    name: "OpenAI",
    description: null,
    is_enabled: false,
    is_implemented: true,
    is_default: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: AIProvider[]): Page<AIProvider> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage(user: User = baseUser) {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter>
          <ToastProvider>
            <AIProviderManagementPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AIProviderManagementPage", () => {
  it("lists providers with code/name/enabled/implemented/default columns", async () => {
    listMock.mockResolvedValueOnce(page([baseProvider({ is_enabled: true, is_default: true })]));
    renderPage();

    expect(await screen.findByText("openai")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Default", { selector: "span" })).toBeInTheDocument();
  });

  it("calls updateAIProvider with is_enabled: true when Enable is clicked", async () => {
    listMock.mockResolvedValue(page([baseProvider({ is_enabled: false, is_implemented: true })]));
    updateMock.mockResolvedValueOnce(baseProvider({ is_enabled: true }));
    renderPage();

    await screen.findByText("OpenAI");
    await userEvent.click(screen.getByRole("button", { name: "Enable" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith("provider-1", { is_enabled: true }));
  });

  it("calls updateAIProvider with is_default: true when Set as default is clicked", async () => {
    listMock.mockResolvedValue(
      page([baseProvider({ is_enabled: true, is_implemented: true, is_default: false })]),
    );
    updateMock.mockResolvedValueOnce(baseProvider({ is_default: true }));
    renderPage();

    await screen.findByText("OpenAI");
    await userEvent.click(screen.getByRole("button", { name: "Set as default" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith("provider-1", { is_default: true }));
  });

  it("disables the Enable button when is_implemented is false", async () => {
    listMock.mockResolvedValueOnce(page([baseProvider({ is_enabled: false, is_implemented: false })]));
    renderPage();

    await screen.findByText("OpenAI");
    expect(screen.getByRole("button", { name: "Enable" })).toBeDisabled();
  });

  it("hides the enable/disable and set-default actions without ai_providers:update", async () => {
    listMock.mockResolvedValueOnce(page([baseProvider({ is_enabled: true, is_implemented: true })]));
    renderPage(readOnlyUser);

    await screen.findByText("OpenAI");
    expect(screen.queryByRole("button", { name: "Disable" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set as default" })).not.toBeInTheDocument();
  });
});
