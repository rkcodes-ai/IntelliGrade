import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { ocrConfigurationsApi } from "@/api/ocrConfigurations";
import { listOCRProviders } from "@/api/ocrProviders";
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
import type { OCRConfiguration } from "@/types/ocr";

interface OCRConfigurationFormState {
  ocr_provider_id: string;
  assessment_id: string;
  language: string;
  confidence_threshold: number | "";
  max_retry_attempts: number;
}

const emptyForm: OCRConfigurationFormState = {
  ocr_provider_id: "",
  assessment_id: "",
  language: "eng",
  confidence_threshold: "",
  max_retry_attempts: 3,
};

function providerLabel(name: string, isImplemented: boolean) {
  return `${name}${isImplemented ? "" : " (not implemented)"}`;
}

/**
 * Standard full-CRUD screen over `OCRConfiguration`, mirroring
 * `AssessmentDashboardPage`'s shape. `ocr_provider_id`/`assessment_id` are
 * fixed at creation (see `OCRConfigurationUpdate`'s doc comment), so those
 * two fields are locked once a row is being edited.
 */
export function OCRConfigurationPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("ocr_configurations:create");
  const canUpdate = permissions.includes("ocr_configurations:update");
  const canDelete = permissions.includes("ocr_configurations:delete");

  const list = usePaginatedList<OCRConfiguration>({
    queryKey: "ocr-configurations",
    fetcher: (params) => ocrConfigurationsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "ocr-configurations",
    ocrConfigurationsApi,
    "OCR Configuration",
  );
  const { data: providers } = useSelectOptions("ocr-providers", () => listOCRProviders({ page_size: 200 }));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<OCRConfiguration | null>(null);
  const [form, setForm] = useState<OCRConfigurationFormState>(emptyForm);
  const [deleting, setDeleting] = useState<OCRConfiguration | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(config: OCRConfiguration) {
    setEditing(config);
    setForm({
      ocr_provider_id: config.ocr_provider_id,
      assessment_id: config.assessment_id ?? "",
      language: config.language,
      confidence_threshold: config.confidence_threshold != null ? Number(config.confidence_threshold) : "",
      max_retry_attempts: config.max_retry_attempts,
    });
    setFormOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const sharedPayload = {
      language: form.language,
      confidence_threshold: form.confidence_threshold === "" ? null : form.confidence_threshold,
      max_retry_attempts: form.max_retry_attempts,
    };
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: sharedPayload }, { onSuccess: () => setFormOpen(false) });
    } else {
      createMutation.mutate(
        {
          ...sharedPayload,
          ocr_provider_id: form.ocr_provider_id,
          assessment_id: form.assessment_id.trim() || null,
        },
        { onSuccess: () => setFormOpen(false) },
      );
    }
  }

  const providerName = (id: string) => providers?.find((provider) => provider.id === id)?.name ?? id;

  const columns: Column<OCRConfiguration>[] = [
    { key: "provider", header: "Provider", render: (row) => providerName(row.ocr_provider_id) },
    {
      key: "scope",
      header: "Scope",
      render: (row) => (row.assessment_id ? row.assessment_id.slice(0, 8) : "Institution default"),
    },
    { key: "language", header: "Language", render: (row) => row.language },
    { key: "max_retries", header: "Max Retries", render: (row) => row.max_retry_attempts },
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
        title="OCR Configurations"
        description="Institution and assessment-level OCR provider configuration."
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
        emptyMessage="No OCR configurations found."
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
        title={editing ? "Edit OCR Configuration" : "New OCR Configuration"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="ocr-config-provider" label="OCR Provider" required>
          <Select
            id="ocr-config-provider"
            required
            disabled={Boolean(editing)}
            value={form.ocr_provider_id}
            onChange={(event) => setForm({ ...form, ocr_provider_id: event.target.value })}
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
          htmlFor="ocr-config-assessment-id"
          label="Assessment ID (optional — leave blank for institution-wide default)"
        >
          <Input
            id="ocr-config-assessment-id"
            disabled={Boolean(editing)}
            value={form.assessment_id}
            onChange={(event) => setForm({ ...form, assessment_id: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="ocr-config-language" label="Language" required>
          <Input
            id="ocr-config-language"
            required
            value={form.language}
            onChange={(event) => setForm({ ...form, language: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="ocr-config-confidence-threshold" label="Confidence Threshold">
          <Input
            id="ocr-config-confidence-threshold"
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={form.confidence_threshold}
            onChange={(event) =>
              setForm({
                ...form,
                confidence_threshold: event.target.value === "" ? "" : Number(event.target.value),
              })
            }
          />
        </FormField>
        <FormField htmlFor="ocr-config-max-retries" label="Max Retry Attempts" required>
          <Input
            id="ocr-config-max-retries"
            type="number"
            required
            min="0"
            value={form.max_retry_attempts}
            onChange={(event) => setForm({ ...form, max_retry_attempts: Number(event.target.value) })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete OCR configuration?"
        description="This configuration will be soft-deleted and can be restored later."
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
