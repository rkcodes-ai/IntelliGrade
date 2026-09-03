import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AIConfigurationPage } from "@/pages/ocr/AIConfigurationPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { AIConfiguration, AIProvider } from "@/types/officialExam";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, createMock, updateMock, removeMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
}));
vi.mock("@/api/aiConfigurations", () => ({
  aiConfigurationsApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
    restore: vi.fn(),
  },
}));

const { providersListMock } = vi.hoisted(() => ({
  providersListMock: vi.fn(),
}));
vi.mock("@/api/aiProviders", () => ({
  listAIProviders: providersListMock,
  getAIProvider: vi.fn(),
  updateAIProvider: vi.fn(),
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
  permissions: [
    "ai_configurations:create",
    "ai_configurations:read",
    "ai_configurations:update",
    "ai_configurations:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const readOnlyUser: User = { ...baseUser, id: "user-2", permissions: ["ai_configurations:read"] };

const provider: AIProvider = {
  id: "provider-1",
  code: "openai",
  name: "OpenAI",
  description: null,
  is_enabled: true,
  is_implemented: true,
  is_default: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const configuration: AIConfiguration = {
  id: "config-1",
  institution_id: "inst-1",
  assessment_id: null,
  ai_provider_id: "provider-1",
  provider_config: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function configPage(items: AIConfiguration[]): Page<AIConfiguration> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function providerPage(items: AIProvider[]): Page<AIProvider> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
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
            <AIConfigurationPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AIConfigurationPage", () => {
  it("lists configurations resolving provider name and scope", async () => {
    listMock.mockResolvedValueOnce(configPage([configuration]));
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage();

    expect(await screen.findByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Institution default")).toBeInTheDocument();
    expect(screen.getByText("Active", { selector: "span" })).toBeInTheDocument();
  });

  it("creates a configuration via the form", async () => {
    listMock.mockResolvedValue(configPage([]));
    providersListMock.mockResolvedValue(providerPage([provider]));
    createMock.mockResolvedValueOnce(configuration);
    renderPage();

    await screen.findByText("No AI configurations found.");
    await userEvent.click(screen.getByRole("button", { name: "New Configuration" }));

    const providerSelect = await screen.findByLabelText(/^AI Provider/);
    await userEvent.selectOptions(providerSelect, "provider-1");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith({
        ai_provider_id: "provider-1",
        assessment_id: null,
        is_active: true,
      }),
    );
  });

  it("edits a configuration via the form", async () => {
    listMock.mockResolvedValue(configPage([configuration]));
    providersListMock.mockResolvedValue(providerPage([provider]));
    updateMock.mockResolvedValueOnce({ ...configuration, is_active: false });
    renderPage();

    await screen.findByText("OpenAI");
    await userEvent.click(screen.getByRole("button", { name: "Edit configuration config-1" }));

    await screen.findByLabelText(/^AI Provider/);
    await userEvent.click(screen.getByLabelText("Active"));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("config-1", {
        assessment_id: null,
        is_active: false,
      }),
    );
  });

  it("deletes a configuration after confirmation", async () => {
    listMock.mockResolvedValue(configPage([configuration]));
    providersListMock.mockResolvedValue(providerPage([provider]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("OpenAI");
    await userEvent.click(screen.getByRole("button", { name: "Delete configuration config-1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("config-1"));
  });

  it("hides create/edit/delete actions without the corresponding permissions", async () => {
    listMock.mockResolvedValueOnce(configPage([configuration]));
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage(readOnlyUser);

    await screen.findByText("OpenAI");
    expect(screen.queryByRole("button", { name: "New Configuration" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit configuration config-1" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete configuration config-1" })).not.toBeInTheDocument();
  });
});
