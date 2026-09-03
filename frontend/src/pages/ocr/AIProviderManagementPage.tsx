import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";

import { listAIProviders, updateAIProvider } from "@/api/aiProviders";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Button } from "@/components/ui/button";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { useAppSelector } from "@/store";
import type { AIProvider, AIProviderUpdate } from "@/types/officialExam";

/**
 * Admin-only screen over the small global AI provider catalog. Rows are
 * seeded by migration (no create/delete, see ADR-041) — only
 * `is_enabled`/`is_default` are patchable, per `AIProviderUpdate`.
 */
export function AIProviderManagementPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canUpdate = permissions.includes("ai_providers:update");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const list = usePaginatedList<AIProvider>({
    queryKey: "ai-providers",
    fetcher: (params) => listAIProviders(params),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: AIProviderUpdate }) => updateAIProvider(id, data),
    onSuccess: () => {
      toast("AI provider updated.", "success");
      void queryClient.invalidateQueries({ queryKey: ["ai-providers"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const columns: Column<AIProvider>[] = [
    { key: "code", header: "Code", render: (row) => row.code },
    { key: "name", header: "Name", render: (row) => row.name },
    {
      key: "enabled",
      header: "Enabled",
      render: (row) => (
        <span className={row.is_enabled ? "text-primary" : "text-muted-foreground"}>
          {row.is_enabled ? "Yes" : "No"}
        </span>
      ),
    },
    {
      key: "implemented",
      header: "Implemented",
      render: (row) => (
        <span className={row.is_implemented ? "text-primary" : "text-muted-foreground"}>
          {row.is_implemented ? "Yes" : "No"}
        </span>
      ),
    },
    {
      key: "default",
      header: "Default",
      render: (row) =>
        row.is_default ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs">
            <Check className="h-3 w-3" />
            Default
          </span>
        ) : (
          canUpdate && (
            <Button
              variant="outline"
              size="sm"
              disabled={updateMutation.isPending}
              onClick={() => updateMutation.mutate({ id: row.id, data: { is_default: true } })}
            >
              Set as default
            </Button>
          )
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="AI Provider Management"
        description="Enable or disable AI providers and choose the institution-wide default."
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search providers..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No AI providers found."
        renderActions={
          canUpdate
            ? (row) => (
                <Button
                  variant={row.is_enabled ? "outline" : "default"}
                  size="sm"
                  // Enabling an unimplemented provider 422s server-side — block it in the UI instead.
                  disabled={updateMutation.isPending || (!row.is_enabled && !row.is_implemented)}
                  onClick={() =>
                    updateMutation.mutate({ id: row.id, data: { is_enabled: !row.is_enabled } })
                  }
                >
                  {row.is_enabled ? "Disable" : "Enable"}
                </Button>
              )
            : undefined
        }
      />

      <PaginationControls
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        totalPages={list.totalPages}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />
    </div>
  );
}
