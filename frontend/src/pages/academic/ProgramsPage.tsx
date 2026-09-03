import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { departmentsApi } from "@/api/departments";
import { programsApi } from "@/api/programs";
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
import type { DegreeType, Program, ProgramCreate } from "@/types/academic";

const DEGREE_TYPES: DegreeType[] = ["ug", "pg", "diploma", "doctorate", "certificate"];

const emptyForm: ProgramCreate = {
  department_id: "",
  name: "",
  code: "",
  degree_type: "ug",
  duration_years: 4,
  total_semesters: 8,
};

export function ProgramsPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("programs:create");
  const canUpdate = permissions.includes("programs:update");
  const canDelete = permissions.includes("programs:delete");

  const list = usePaginatedList<Program>({
    queryKey: "programs",
    fetcher: (params) => programsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "programs",
    programsApi,
    "Program",
  );
  const { data: departments } = useSelectOptions("departments", () =>
    departmentsApi.list({ page_size: 200 }),
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Program | null>(null);
  const [form, setForm] = useState<ProgramCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Program | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(program: Program) {
    setEditing(program);
    setForm({
      department_id: program.department_id,
      name: program.name,
      code: program.code,
      degree_type: program.degree_type as DegreeType,
      duration_years: program.duration_years,
      total_semesters: program.total_semesters,
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

  const departmentName = (id: string) => departments?.find((d) => d.id === id)?.name ?? id;

  const columns: Column<Program>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "code", header: "Code", render: (row) => row.code },
    { key: "department", header: "Department", render: (row) => departmentName(row.department_id) },
    { key: "degree", header: "Degree", render: (row) => row.degree_type },
    { key: "duration", header: "Duration (yrs)", render: (row) => row.duration_years },
  ];

  return (
    <div>
      <PageHeader
        title="Programs"
        description="Manage degree programs offered by your departments."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Program
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search programs..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No programs found."
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
        title={editing ? "Edit Program" : "New Program"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="program-department" label="Department" required>
          <Select
            id="program-department"
            required
            value={form.department_id}
            onChange={(event) => setForm({ ...form, department_id: event.target.value })}
          >
            <option value="" disabled>
              Select a department
            </option>
            {departments?.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="program-name" label="Name" required>
          <Input
            id="program-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="program-code" label="Code" required>
          <Input
            id="program-code"
            required
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
        </FormField>
        <FormField htmlFor="program-degree" label="Degree Type" required>
          <Select
            id="program-degree"
            required
            value={form.degree_type}
            onChange={(event) => setForm({ ...form, degree_type: event.target.value as DegreeType })}
          >
            {DEGREE_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="program-duration" label="Duration (years)" required>
          <Input
            id="program-duration"
            type="number"
            min={1}
            max={10}
            required
            value={form.duration_years}
            onChange={(event) => setForm({ ...form, duration_years: Number(event.target.value) })}
          />
        </FormField>
        <FormField htmlFor="program-semesters" label="Total Semesters" required>
          <Input
            id="program-semesters"
            type="number"
            min={1}
            max={20}
            required
            value={form.total_semesters}
            onChange={(event) => setForm({ ...form, total_semesters: Number(event.target.value) })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete program?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
