import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import { InstitutionSwitcher } from "@/components/layout/InstitutionSwitcher";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Institution } from "@/types/academic";

const { listMyInstitutionsMock } = vi.hoisted(() => ({ listMyInstitutionsMock: vi.fn() }));
vi.mock("@/api/institutions", () => ({ listMyInstitutions: listMyInstitutionsMock }));

const institutions: Institution[] = [
  {
    id: "inst-1",
    name: "Acme University",
    code: "ACME",
    institution_type: "university",
    address: null,
    city: null,
    state: null,
    country: null,
    postal_code: null,
    phone: null,
    email: null,
    website: null,
    established_year: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "inst-2",
    name: "Second College",
    code: "SECOND",
    institution_type: "college",
    address: null,
    city: null,
    state: null,
    country: null,
    postal_code: null,
    phone: null,
    email: null,
    website: null,
    established_year: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function renderSwitcher(currentInstitutionId: string | null = null) {
  const store = configureStore({
    reducer: { institution: institutionReducer },
    preloadedState: { institution: { currentInstitutionId } },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <InstitutionSwitcher />
      </Provider>
    </QueryClientProvider>,
  );
  return store;
}

describe("InstitutionSwitcher", () => {
  it("renders nothing while loading or with zero institutions", () => {
    listMyInstitutionsMock.mockResolvedValueOnce([]);
    const { container } = render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Provider
          store={configureStore({
            reducer: { institution: institutionReducer },
            preloadedState: { institution: { currentInstitutionId: null } },
          })}
        >
          <InstitutionSwitcher />
        </Provider>
      </QueryClientProvider>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a plain label when there is exactly one institution", async () => {
    listMyInstitutionsMock.mockResolvedValueOnce([institutions[0]]);
    renderSwitcher();
    expect(await screen.findByText("Acme University")).toBeInTheDocument();
  });

  it("shows a select and switches the current institution when there are several", async () => {
    listMyInstitutionsMock.mockResolvedValueOnce(institutions);
    const store = renderSwitcher();

    const select = await screen.findByLabelText("Current institution");
    await waitFor(() => expect(store.getState().institution.currentInstitutionId).toBe("inst-1"));

    await userEvent.selectOptions(select, "inst-2");
    expect(store.getState().institution.currentInstitutionId).toBe("inst-2");
  });
});
