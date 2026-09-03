import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { academicYearsApi } from "@/api/academicYears";
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
import type { AcademicYear, AcademicYearCreate, AcademicYearStatus } from "@/types/academic";

const STATUSES: AcademicYearStatus[] = ["planned", "active", "completed", "archived"];

const emptyForm: AcademicYearCreate = {
  year_label: "",
  start_date: "",
  end_date: "",
  is_current: false,
  status: "planned",
};

export function AcademicYearsPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("academic_years:create");
  const canUpdate = permissions.includes("academic_years:update");
  const canDelete = permissions.includes("academic_years:delete");

  const list = usePaginatedList<AcademicYear>({
    queryKey: "academic-years",
    fetcher: (params) => academicYearsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "academic-years",
    academicYearsApi,
    "Academic Year",
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AcademicYear | null>(null);
  const [form, setForm] = useState<AcademicYearCreate>(emptyForm);
  const [deleting, setDeleting] = useState<AcademicYear | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(year: AcademicYear) {
    setEditing(year);
    setForm({
      year_label: year.year_label,
      start_date: year.start_date,
      end_date: year.end_date,
      is_current: year.is_current,
      status: year.status as AcademicYearStatus,
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

  const columns: Column<AcademicYear>[] = [
    { key: "label", header: "Year", render: (row) => row.year_label },
    { key: "start", header: "Start", render: (row) => row.start_date },
    { key: "end", header: "End", render: (row) => row.end_date },
    { key: "status", header: "Status", render: (row) => row.status },
    { key: "current", header: "Current", render: (row) => (row.is_current ? "Yes" : "No") },
  ];

  return (
    <div>
      <PageHeader
        title="Academic Years"
        description="Manage academic year cycles for your institution."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Academic Year
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search academic years..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No academic years found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit ${row.year_label}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${row.year_label}`}
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
        title={editing ? "Edit Academic Year" : "New Academic Year"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="year-label" label="Year Label" required>
          <Input
            id="year-label"
            required
            placeholder="2026-2027"
            value={form.year_label}
            onChange={(event) => setForm({ ...form, year_label: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="year-start" label="Start Date" required>
          <Input
            id="year-start"
            type="date"
            required
            value={form.start_date}
            onChange={(event) => setForm({ ...form, start_date: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="year-end" label="End Date" required>
          <Input
            id="year-end"
            type="date"
            required
            value={form.end_date}
            onChange={(event) => setForm({ ...form, end_date: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="year-status" label="Status" required>
          <Select
            id="year-status"
            required
            value={form.status}
            onChange={(event) => setForm({ ...form, status: event.target.value as AcademicYearStatus })}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </Select>
        </FormField>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_current ?? false}
            onChange={(event) => setForm({ ...form, is_current: event.target.checked })}
          />
          Current academic year
        </label>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete academic year?"
        description={`"${deleting?.year_label}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
