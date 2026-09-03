import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { institutionsApi } from "@/api/institutions";
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
import { useAppSelector } from "@/store";
import type { Institution, InstitutionCreate } from "@/types/academic";

const INSTITUTION_TYPES = ["university", "college", "school", "institute"] as const;

const emptyForm: InstitutionCreate = {
  name: "",
  code: "",
  institution_type: "university",
  city: "",
};

export function InstitutionsPage() {
  const canCreate = useAppSelector((state) => state.auth.user?.permissions.includes("institutions:create"));
  const canUpdate = useAppSelector((state) => state.auth.user?.permissions.includes("institutions:update"));
  const canDelete = useAppSelector((state) => state.auth.user?.permissions.includes("institutions:delete"));

  const list = usePaginatedList<Institution>({
    queryKey: "institutions",
    fetcher: (params) => institutionsApi.list(params),
    requiresInstitution: false,
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "institutions",
    institutionsApi,
    "Institution",
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Institution | null>(null);
  const [form, setForm] = useState<InstitutionCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Institution | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(institution: Institution) {
    setEditing(institution);
    setForm({
      name: institution.name,
      code: institution.code,
      institution_type: institution.institution_type,
      city: institution.city ?? "",
    });
    setFormOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(
        { id: editing.id, data: form },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createMutation.mutate(form, { onSuccess: () => setFormOpen(false) });
    }
  }

  const columns: Column<Institution>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "code", header: "Code", render: (row) => row.code },
    { key: "type", header: "Type", render: (row) => row.institution_type },
    { key: "city", header: "City", render: (row) => row.city ?? "—" },
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
        title="Institutions"
        description="Manage tenant institutions on the platform."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Institution
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search institutions..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No institutions found."
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
        title={editing ? "Edit Institution" : "New Institution"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="inst-name" label="Name" required>
          <Input
            id="inst-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="inst-code" label="Code" required>
          <Input
            id="inst-code"
            required
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
        </FormField>
        <FormField htmlFor="inst-type" label="Type" required>
          <Select
            id="inst-type"
            required
            value={form.institution_type}
            onChange={(event) => setForm({ ...form, institution_type: event.target.value })}
          >
            {INSTITUTION_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="inst-city" label="City">
          <Input
            id="inst-city"
            value={form.city ?? ""}
            onChange={(event) => setForm({ ...form, city: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete institution?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() =>
          deleting &&
          removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })
        }
      />
    </div>
  );
}
