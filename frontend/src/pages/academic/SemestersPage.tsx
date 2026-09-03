import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { academicYearsApi } from "@/api/academicYears";
import { semestersApi } from "@/api/semesters";
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
import type { Semester, SemesterCreate, SemesterTermType } from "@/types/academic";

const TERM_TYPES: SemesterTermType[] = ["odd", "even"];

const emptyForm: SemesterCreate = {
  academic_year_id: "",
  name: "",
  semester_number: 1,
  term_type: "odd",
  start_date: "",
  end_date: "",
  status: "planned",
};

export function SemestersPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("semesters:create");
  const canUpdate = permissions.includes("semesters:update");
  const canDelete = permissions.includes("semesters:delete");

  const list = usePaginatedList<Semester>({
    queryKey: "semesters",
    fetcher: (params) => semestersApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "semesters",
    semestersApi,
    "Semester",
  );
  const { data: academicYears } = useSelectOptions("academic-years", () =>
    academicYearsApi.list({ page_size: 200 }),
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Semester | null>(null);
  const [form, setForm] = useState<SemesterCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Semester | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(semester: Semester) {
    setEditing(semester);
    setForm({
      academic_year_id: semester.academic_year_id,
      name: semester.name,
      semester_number: semester.semester_number,
      term_type: semester.term_type as SemesterTermType,
      start_date: semester.start_date,
      end_date: semester.end_date,
      status: semester.status as SemesterCreate["status"],
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

  const yearLabel = (id: string) => academicYears?.find((y) => y.id === id)?.year_label ?? id;

  const columns: Column<Semester>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "number", header: "#", render: (row) => row.semester_number },
    { key: "year", header: "Academic Year", render: (row) => yearLabel(row.academic_year_id) },
    { key: "term", header: "Term", render: (row) => row.term_type },
    { key: "status", header: "Status", render: (row) => row.status },
  ];

  return (
    <div>
      <PageHeader
        title="Semesters"
        description="Manage semesters within each academic year."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Semester
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search semesters..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No semesters found."
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
        title={editing ? "Edit Semester" : "New Semester"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="semester-year" label="Academic Year" required>
          <Select
            id="semester-year"
            required
            value={form.academic_year_id}
            onChange={(event) => setForm({ ...form, academic_year_id: event.target.value })}
          >
            <option value="" disabled>
              Select an academic year
            </option>
            {academicYears?.map((year) => (
              <option key={year.id} value={year.id}>
                {year.year_label}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="semester-name" label="Name" required>
          <Input
            id="semester-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="semester-number" label="Semester Number" required>
          <Input
            id="semester-number"
            type="number"
            min={1}
            max={20}
            required
            value={form.semester_number}
            onChange={(event) => setForm({ ...form, semester_number: Number(event.target.value) })}
          />
        </FormField>
        <FormField htmlFor="semester-term" label="Term Type" required>
          <Select
            id="semester-term"
            required
            value={form.term_type}
            onChange={(event) => setForm({ ...form, term_type: event.target.value as SemesterTermType })}
          >
            {TERM_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="semester-start" label="Start Date" required>
          <Input
            id="semester-start"
            type="date"
            required
            value={form.start_date}
            onChange={(event) => setForm({ ...form, start_date: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="semester-end" label="End Date" required>
          <Input
            id="semester-end"
            type="date"
            required
            value={form.end_date}
            onChange={(event) => setForm({ ...form, end_date: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete semester?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
