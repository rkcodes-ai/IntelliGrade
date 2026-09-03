import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { campusesApi } from "@/api/campuses";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useAppSelector } from "@/store";
import type { Campus, CampusCreate } from "@/types/academic";

const emptyForm: CampusCreate = { name: "", code: "", city: "", is_main_campus: false };

export function CampusesPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("campuses:create");
  const canUpdate = permissions.includes("campuses:update");
  const canDelete = permissions.includes("campuses:delete");

  const list = usePaginatedList<Campus>({
    queryKey: "campuses",
    fetcher: (params) => campusesApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "campuses",
    campusesApi,
    "Campus",
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Campus | null>(null);
  const [form, setForm] = useState<CampusCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Campus | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(campus: Campus) {
    setEditing(campus);
    setForm({
      name: campus.name,
      code: campus.code,
      city: campus.city ?? "",
      is_main_campus: campus.is_main_campus,
    });
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

  const columns: Column<Campus>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "code", header: "Code", render: (row) => row.code },
    { key: "city", header: "City", render: (row) => row.city ?? "—" },
    { key: "main", header: "Main", render: (row) => (row.is_main_campus ? "Yes" : "No") },
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
        title="Campuses"
        description="Manage physical campuses within your institution."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Campus
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search campuses..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No campuses found."
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
        title={editing ? "Edit Campus" : "New Campus"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="campus-name" label="Name" required>
          <Input
            id="campus-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="campus-code" label="Code" required>
          <Input
            id="campus-code"
            required
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
        </FormField>
        <FormField htmlFor="campus-city" label="City">
          <Input
            id="campus-city"
            value={form.city ?? ""}
            onChange={(event) => setForm({ ...form, city: event.target.value })}
          />
        </FormField>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_main_campus ?? false}
            onChange={(event) => setForm({ ...form, is_main_campus: event.target.checked })}
          />
          Main campus
        </label>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete campus?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
