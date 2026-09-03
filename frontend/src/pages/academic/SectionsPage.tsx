import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { listBatches } from "@/api/batches";
import { sectionsApi } from "@/api/sections";
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
import type { Section, SectionCreate } from "@/types/academic";

const emptyForm: SectionCreate = { batch_id: "", name: "", max_capacity: 60 };

export function SectionsPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("sections:create");
  const canUpdate = permissions.includes("sections:update");
  const canDelete = permissions.includes("sections:delete");

  const list = usePaginatedList<Section>({
    queryKey: "sections",
    fetcher: (params) => sectionsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "sections",
    sectionsApi,
    "Section",
  );
  const { data: batches } = useSelectOptions("batches", () => listBatches({ page_size: 200 }));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Section | null>(null);
  const [form, setForm] = useState<SectionCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Section | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(section: Section) {
    setEditing(section);
    setForm({ batch_id: section.batch_id, name: section.name, max_capacity: section.max_capacity });
    setFormOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: form }, { onSuccess: () => setFormOpen(false) });
    } else {
      createMutation.mutate(form, { onSuccess: () => setFormOpen(false) });
    }
  }

  const batchName = (id: string) => batches?.find((b) => b.id === id)?.name ?? id;

  const columns: Column<Section>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "batch", header: "Batch", render: (row) => batchName(row.batch_id) },
    { key: "capacity", header: "Max Capacity", render: (row) => row.max_capacity },
    {
      key: "status",
      header: "Status",
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
        title="Sections"
        description="Manage batch subdivisions (sections)."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Section
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search sections..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No sections found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button variant="ghost" size="icon" aria-label={`Edit ${row.name}`} onClick={() => openEdit(row)}>
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${row.name}`}
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
        title={editing ? "Edit Section" : "New Section"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="section-batch" label="Batch" required>
          <Select
            id="section-batch"
            required
            value={form.batch_id}
            onChange={(event) => setForm({ ...form, batch_id: event.target.value })}
          >
            <option value="" disabled>
              Select a batch
            </option>
            {batches?.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="section-name" label="Name" required>
          <Input
            id="section-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="section-capacity" label="Max Capacity" required>
          <Input
            id="section-capacity"
            type="number"
            min={1}
            required
            value={form.max_capacity}
            onChange={(event) => setForm({ ...form, max_capacity: Number(event.target.value) })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete section?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
