import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { aiConfigurationsApi } from "@/api/aiConfigurations";
import { listAIProviders } from "@/api/aiProviders";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { useAppSelector } from "@/store";
import type { AIConfiguration } from "@/types/officialExam";

interface AIConfigurationFormState {
  ai_provider_id: string;
  assessment_id: string;
  is_active: boolean;
}

const emptyForm: AIConfigurationFormState = {
  ai_provider_id: "",
  assessment_id: "",
  is_active: true,
};

function providerLabel(name: string, isImplemented: boolean) {
  return `${name}${isImplemented ? "" : " (not implemented)"}`;
}

/**
 * Standard full-CRUD screen over `AIConfiguration`, mirroring
 * `OCRConfigurationPage`'s shape. `ai_provider_id` is fixed at creation
 * (see `AIConfigurationUpdate`'s doc comment), so it is locked once a row
 * is being edited; `assessment_id`/`is_active` remain editable.
 */
export function AIConfigurationPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("ai_configurations:create");
  const canUpdate = permissions.includes("ai_configurations:update");
  const canDelete = permissions.includes("ai_configurations:delete");

  const list = usePaginatedList<AIConfiguration>({
    queryKey: "ai-configurations",
    fetcher: (params) => aiConfigurationsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "ai-configurations",
    aiConfigurationsApi,
    "AI Configuration",
  );
  const { data: providers } = useSelectOptions("ai-providers", () => listAIProviders({ page_size: 200 }));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AIConfiguration | null>(null);
  const [form, setForm] = useState<AIConfigurationFormState>(emptyForm);
  const [deleting, setDeleting] = useState<AIConfiguration | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(config: AIConfiguration) {
    setEditing(config);
    setForm({
      ai_provider_id: config.ai_provider_id,
      assessment_id: config.assessment_id ?? "",
      is_active: config.is_active,
    });
    setFormOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(
        {
          id: editing.id,
          data: {
            assessment_id: form.assessment_id.trim() || null,
            is_active: form.is_active,
          },
        },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createMutation.mutate(
        {
          ai_provider_id: form.ai_provider_id,
          assessment_id: form.assessment_id.trim() || null,
          is_active: form.is_active,
        },
        { onSuccess: () => setFormOpen(false) },
      );
    }
  }

  const providerName = (id: string) => providers?.find((provider) => provider.id === id)?.name ?? id;

  const columns: Column<AIConfiguration>[] = [
    { key: "provider", header: "Provider", render: (row) => providerName(row.ai_provider_id) },
    {
      key: "scope",
      header: "Scope",
      render: (row) => (row.assessment_id ? row.assessment_id.slice(0, 8) : "Institution default"),
    },
    {
      key: "active",
      header: "Active",
      render: (row) => (
        <span className={row.is_active ? "text-primary" : "text-muted-foreground"}>
          {row.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="AI Configurations"
        description="Institution and assessment-level AI provider configuration."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Configuration
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search configurations..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No AI configurations found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit configuration ${row.id}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete configuration ${row.id}`}
                onClick={() => setDeleting(row)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      />

      <PaginationControls
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        totalPages={list.totalPages}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />

      <FormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editing ? "Edit AI Configuration" : "New AI Configuration"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="ai-config-provider" label="AI Provider" required>
          <Select
            id="ai-config-provider"
            required
            disabled={Boolean(editing)}
            value={form.ai_provider_id}
            onChange={(event) => setForm({ ...form, ai_provider_id: event.target.value })}
          >
            <option value="" disabled>
              Select a provider
            </option>
            {providers?.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {providerLabel(provider.name, provider.is_implemented)}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField
          htmlFor="ai-config-assessment-id"
          label="Assessment ID (optional — leave blank for institution-wide default)"
        >
          <Input
            id="ai-config-assessment-id"
            value={form.assessment_id}
            onChange={(event) => setForm({ ...form, assessment_id: event.target.value })}
          />
        </FormField>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={form.is_active}
            onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
          />
          Active
        </label>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete AI configuration?"
        description="This configuration will be soft-deleted and can be restored later."
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
