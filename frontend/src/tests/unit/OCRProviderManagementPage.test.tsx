import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { OCRProviderManagementPage } from "@/pages/ocr/OCRProviderManagementPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { OCRProvider } from "@/types/ocr";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, updateMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  updateMock: vi.fn(),
}));
vi.mock("@/api/ocrProviders", () => ({
  listOCRProviders: listMock,
  getOCRProvider: vi.fn(),
  updateOCRProvider: updateMock,
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
  permissions: ["ocr_providers:update"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function baseProvider(overrides: Partial<OCRProvider> = {}): OCRProvider {
  return {
    id: "provider-1",
    code: "tesseract",
    name: "Tesseract",
    description: null,
    is_enabled: false,
    is_implemented: true,
    is_default: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: OCRProvider[]): Page<OCRProvider> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
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
            <OCRProviderManagementPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("OCRProviderManagementPage", () => {
  it("lists providers with code/name/enabled/implemented/default columns", async () => {
    listMock.mockResolvedValueOnce(
      page([baseProvider({ is_enabled: true, is_default: true })]),
    );
    renderPage();

    expect(await screen.findByText("tesseract")).toBeInTheDocument();
    expect(screen.getByText("Tesseract")).toBeInTheDocument();
    expect(screen.getByText("Default", { selector: "span" })).toBeInTheDocument();
  });

  it("calls updateOCRProvider with is_enabled: true when Enable is clicked", async () => {
    listMock.mockResolvedValue(page([baseProvider({ is_enabled: false, is_implemented: true })]));
    updateMock.mockResolvedValueOnce(baseProvider({ is_enabled: true }));
    renderPage();

    await screen.findByText("Tesseract");
    await userEvent.click(screen.getByRole("button", { name: "Enable" }));
    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("provider-1", { is_enabled: true }),
    );
  });

  it("calls updateOCRProvider with is_enabled: false when Disable is clicked", async () => {
    listMock.mockResolvedValue(page([baseProvider({ is_enabled: true, is_implemented: true })]));
    updateMock.mockResolvedValueOnce(baseProvider({ is_enabled: false }));
    renderPage();

    await screen.findByText("Tesseract");
    await userEvent.click(screen.getByRole("button", { name: "Disable" }));
    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("provider-1", { is_enabled: false }),
    );
  });

  it("calls updateOCRProvider with is_default: true when Set as default is clicked", async () => {
    listMock.mockResolvedValue(
      page([baseProvider({ is_enabled: true, is_implemented: true, is_default: false })]),
    );
    updateMock.mockResolvedValueOnce(baseProvider({ is_default: true }));
    renderPage();

    await screen.findByText("Tesseract");
    await userEvent.click(screen.getByRole("button", { name: "Set as default" }));
    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("provider-1", { is_default: true }),
    );
  });

  it("disables the Enable button when is_implemented is false", async () => {
    listMock.mockResolvedValueOnce(page([baseProvider({ is_enabled: false, is_implemented: false })]));
    renderPage();

    await screen.findByText("Tesseract");
    expect(screen.getByRole("button", { name: "Enable" })).toBeDisabled();
  });
});
