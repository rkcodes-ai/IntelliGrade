import type { ReactNode } from "react";
import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { ToastProvider } from "@/context/ToastProvider";
import institutionReducer from "@/store/slices/institutionSlice";
import type { CrudApi } from "@/api/createCrudApi";
import type { Page } from "@/types/pagination";

function createWrapper(currentInstitutionId: string | null = "inst-1") {
  const store = configureStore({
    reducer: { institution: institutionReducer },
    preloadedState: { institution: { currentInstitutionId } },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <Provider store={store}>
          <ToastProvider>{children}</ToastProvider>
        </Provider>
      </QueryClientProvider>
    );
  }
  return Wrapper;
}

const page = <T,>(items: T[]): Page<T> => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  total_pages: 1,
});

describe("usePaginatedList", () => {
  it("does not fetch when no institution is selected and requiresInstitution is true", () => {
    const fetcher = vi.fn().mockResolvedValue(page([]));
    const { result } = renderHook(
      () => usePaginatedList({ queryKey: "widgets", fetcher }),
      { wrapper: createWrapper(null) },
    );
    // Disabled queries (no institution selected yet) sit in TanStack
    // Query's "pending, idle fetchStatus" state — `isLoading` is actually
    // `false` here since it requires an in-flight fetch, so assert on the
    // fetcher never having been called instead.
    expect(result.current.items).toEqual([]);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("fetches once an institution is selected and exposes page state", async () => {
    const fetcher = vi.fn().mockResolvedValue(page([{ id: "1" }]));
    const { result } = renderHook(
      () => usePaginatedList({ queryKey: "widgets", fetcher }),
      { wrapper: createWrapper("inst-1") },
    );

    await waitFor(() => expect(result.current.items).toHaveLength(1));
    expect(fetcher).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20, sort_order: "desc" }),
    );
  });

  it("resets to page 1 when search changes", async () => {
    const fetcher = vi.fn().mockResolvedValue(page([]));
    const { result } = renderHook(
      () => usePaginatedList({ queryKey: "widgets", fetcher }),
      { wrapper: createWrapper("inst-1") },
    );
    await waitFor(() => expect(fetcher).toHaveBeenCalled());

    act(() => result.current.setPage(2));
    expect(result.current.page).toBe(2);

    act(() => result.current.setSearch("acme"));
    expect(result.current.page).toBe(1);
    expect(result.current.search).toBe("acme");
  });

  it("toggleSort flips order on the same field and resets on a new field", async () => {
    const fetcher = vi.fn().mockResolvedValue(page([]));
    const { result } = renderHook(
      () => usePaginatedList({ queryKey: "widgets", fetcher, defaultSortBy: "name" }),
      { wrapper: createWrapper("inst-1") },
    );
    await waitFor(() => expect(fetcher).toHaveBeenCalled());

    act(() => result.current.toggleSort("name"));
    expect(result.current.sortBy).toBe("name");
    expect(result.current.sortOrder).toBe("asc");

    act(() => result.current.toggleSort("code"));
    expect(result.current.sortBy).toBe("code");
    expect(result.current.sortOrder).toBe("asc");
  });

  it("requiresInstitution: false fetches even without a selected institution", async () => {
    const fetcher = vi.fn().mockResolvedValue(page([{ id: "1" }]));
    const { result } = renderHook(
      () => usePaginatedList({ queryKey: "institutions", fetcher, requiresInstitution: false }),
      { wrapper: createWrapper(null) },
    );
    await waitFor(() => expect(result.current.items).toHaveLength(1));
  });
});

describe("useSelectOptions", () => {
  it("returns the items array from the page response", async () => {
    const fetcher = vi.fn().mockResolvedValue(page([{ id: "c1", name: "Campus" }]));
    const { result } = renderHook(
      () => useSelectOptions<{ id: string; name: string }>("campuses", fetcher),
      { wrapper: createWrapper("inst-1") },
    );
    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(result.current.data?.[0].name).toBe("Campus");
  });

  it("does not fetch without a selected institution", () => {
    const fetcher = vi.fn().mockResolvedValue(page([]));
    renderHook(() => useSelectOptions("campuses", fetcher), { wrapper: createWrapper(null) });
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("useCrudMutations", () => {
  interface Widget {
    id: string;
    name: string;
  }

  function makeApi(): CrudApi<Widget, { name: string }, { name?: string }> {
    return {
      list: vi.fn(),
      listDeleted: vi.fn(),
      get: vi.fn(),
      create: vi.fn().mockResolvedValue({ id: "1", name: "New" }),
      update: vi.fn().mockResolvedValue({ id: "1", name: "Updated" }),
      remove: vi.fn().mockResolvedValue(undefined),
      restore: vi.fn().mockResolvedValue({ id: "1", name: "New" }),
    };
  }

  it("create/update/remove/restore call through to the api and settle successfully", async () => {
    const api = makeApi();
    const { result } = renderHook(() => useCrudMutations("widgets", api, "Widget"), {
      wrapper: createWrapper("inst-1"),
    });

    await act(async () => {
      await result.current.createMutation.mutateAsync({ name: "New" });
    });
    expect(api.create).toHaveBeenCalledWith({ name: "New" });

    await act(async () => {
      await result.current.updateMutation.mutateAsync({ id: "1", data: { name: "Updated" } });
    });
    expect(api.update).toHaveBeenCalledWith("1", { name: "Updated" });

    await act(async () => {
      await result.current.removeMutation.mutateAsync("1");
    });
    expect(api.remove).toHaveBeenCalledWith("1");

    await act(async () => {
      await result.current.restoreMutation.mutateAsync("1");
    });
    expect(api.restore).toHaveBeenCalledWith("1");
  });

  it("surfaces an error toast state when create fails", async () => {
    const api = makeApi();
    (api.create as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("boom"));
    const { result } = renderHook(() => useCrudMutations("widgets", api, "Widget"), {
      wrapper: createWrapper("inst-1"),
    });

    await act(async () => {
      await result.current.createMutation.mutateAsync({ name: "New" }).catch(() => undefined);
    });
    await waitFor(() => expect(result.current.createMutation.isError).toBe(true));
  });
});
