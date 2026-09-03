import { useQueryClient, useMutation } from "@tanstack/react-query";

import type { CrudApi } from "@/api/createCrudApi";
import { useToast } from "@/context/ToastProvider";
import { extractErrorMessage } from "@/lib/errors";

/**
 * Wires an entity's `CrudApi` (see `api/createCrudApi.ts`) to create/update/
 * delete/restore mutations that toast on success/error and invalidate the
 * entity's list queries — the boilerplate every management page otherwise
 * repeats by hand (matches the inline `useMutation` pattern established in
 * `SessionsPage.tsx`, just factored out since eleven pages share it).
 */
export function useCrudMutations<TRead, TCreate, TUpdate>(
  queryKey: string,
  api: CrudApi<TRead, TCreate, TUpdate>,
  entityLabel: string,
) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: [queryKey] });
  }

  const createMutation = useMutation({
    mutationFn: (data: TCreate) => api.create(data),
    onSuccess: () => {
      toast(`${entityLabel} created.`, "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: TUpdate }) => api.update(id, data),
    onSuccess: () => {
      toast(`${entityLabel} updated.`, "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => api.remove(id),
    onSuccess: () => {
      toast(`${entityLabel} deleted.`, "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const restoreMutation = useMutation({
    mutationFn: (id: string) => api.restore(id),
    onSuccess: () => {
      toast(`${entityLabel} restored.`, "success");
      void invalidate();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  return { createMutation, updateMutation, removeMutation, restoreMutation };
}
