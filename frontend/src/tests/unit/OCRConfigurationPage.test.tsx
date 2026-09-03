import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { OCRConfigurationPage } from "@/pages/ocr/OCRConfigurationPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { OCRConfiguration, OCRProvider } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, createMock, updateMock, removeMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
}));
vi.mock("@/api/ocrConfigurations", () => ({
  ocrConfigurationsApi: {
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
vi.mock("@/api/ocrProviders", () => ({
  listOCRProviders: providersListMock,
  getOCRProvider: vi.fn(),
  updateOCRProvider: vi.fn(),
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
    "ocr_configurations:create",
    "ocr_configurations:read",
    "ocr_configurations:update",
    "ocr_configurations:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const provider: OCRProvider = {
  id: "provider-1",
  code: "tesseract",
  name: "Tesseract",
  description: null,
  is_enabled: true,
  is_implemented: true,
  is_default: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const configuration: OCRConfiguration = {
  id: "config-1",
  institution_id: "inst-1",
  assessment_id: null,
  ocr_provider_id: "provider-1",
  language: "eng",
  confidence_threshold: "0.80",
  preprocessing_steps: null,
  max_retry_attempts: 3,
  is_active: true,
  is_ensemble_enabled: false,
  ensemble_provider_codes: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function configPage(items: OCRConfiguration[]): Page<OCRConfiguration> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function providerPage(items: OCRProvider[]): Page<OCRProvider> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
}

function renderPage() {
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
        <MemoryRouter>
          <ToastProvider>
            <OCRConfigurationPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("OCRConfigurationPage", () => {
  it("lists configurations resolving provider name and scope", async () => {
    listMock.mockResolvedValueOnce(configPage([configuration]));
    providersListMock.mockResolvedValueOnce(providerPage([provider]));
    renderPage();

    expect(await screen.findByText("Tesseract")).toBeInTheDocument();
    expect(screen.getByText("Institution default")).toBeInTheDocument();
    expect(screen.getByText("eng")).toBeInTheDocument();
  });

  it("creates a configuration via the form", async () => {
    listMock.mockResolvedValue(configPage([]));
    providersListMock.mockResolvedValue(providerPage([provider]));
    createMock.mockResolvedValueOnce(configuration);
    renderPage();

    await screen.findByText("No OCR configurations found.");
    await userEvent.click(screen.getByRole("button", { name: "New Configuration" }));

    const providerSelect = await screen.findByLabelText(/^OCR Provider/);
    await userEvent.selectOptions(providerSelect, "provider-1");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith({
        language: "eng",
        confidence_threshold: null,
        max_retry_attempts: 3,
        ocr_provider_id: "provider-1",
        assessment_id: null,
      }),
    );
  });

  it("edits a configuration via the form", async () => {
    listMock.mockResolvedValue(configPage([configuration]));
    providersListMock.mockResolvedValue(providerPage([provider]));
    updateMock.mockResolvedValueOnce({ ...configuration, language: "spa" });
    renderPage();

    await screen.findByText("Tesseract");
    await userEvent.click(screen.getByRole("button", { name: "Edit configuration config-1" }));

    const languageInput = await screen.findByLabelText(/^Language/);
    await userEvent.clear(languageInput);
    await userEvent.type(languageInput, "spa");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("config-1", {
        language: "spa",
        confidence_threshold: 0.8,
        max_retry_attempts: 3,
      }),
    );
  });

  it("deletes a configuration after confirmation", async () => {
    listMock.mockResolvedValue(configPage([configuration]));
    providersListMock.mockResolvedValue(providerPage([provider]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Tesseract");
    await userEvent.click(screen.getByRole("button", { name: "Delete configuration config-1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("config-1"));
  });
});
