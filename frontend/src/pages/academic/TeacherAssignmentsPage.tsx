import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { listSubjectAllocations } from "@/api/subjectAllocations";
import { teacherAssignmentsApi } from "@/api/teacherAssignments";
import { listUsers } from "@/api/users";
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
import type { AssignmentRole, TeacherAssignment, TeacherAssignmentCreate } from "@/types/academic";

const ROLES: AssignmentRole[] = ["primary", "assistant", "substitute"];

const emptyForm: TeacherAssignmentCreate = {
  teacher_user_id: "",
  subject_allocation_id: "",
  assignment_role: "primary",
  assigned_from: "",
  assigned_to: null,
};

export function TeacherAssignmentsPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("teacher_assignments:create");
  const canUpdate = permissions.includes("teacher_assignments:update");
  const canDelete = permissions.includes("teacher_assignments:delete");

  const list = usePaginatedList<TeacherAssignment>({
    queryKey: "teacher-assignments",
    fetcher: (params) => teacherAssignmentsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "teacher-assignments",
    teacherAssignmentsApi,
    "Teacher Assignment",
  );
  const { data: allocations } = useSelectOptions("subject-allocations", () =>
    listSubjectAllocations({ page_size: 200 }),
  );
  const { data: users } = useQuery({
    queryKey: ["users", "teachers-for-select"],
    queryFn: () => listUsers({ limit: 200 }),
  });
  const teachers = users?.filter((user) => user.roles.includes("teacher"));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<TeacherAssignment | null>(null);
  const [form, setForm] = useState<TeacherAssignmentCreate>(emptyForm);
  const [deleting, setDeleting] = useState<TeacherAssignment | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(assignment: TeacherAssignment) {
    setEditing(assignment);
    setForm({
      teacher_user_id: assignment.teacher_user_id,
      subject_allocation_id: assignment.subject_allocation_id,
      assignment_role: assignment.assignment_role as AssignmentRole,
      assigned_from: assignment.assigned_from,
      assigned_to: assignment.assigned_to,
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

  const teacherName = (id: string) => {
    const teacher = teachers?.find((t) => t.id === id);
    return teacher ? teacher.full_name : id;
  };

  const columns: Column<TeacherAssignment>[] = [
    { key: "teacher", header: "Teacher", render: (row) => teacherName(row.teacher_user_id) },
    { key: "role", header: "Role", render: (row) => row.assignment_role },
    { key: "from", header: "From", render: (row) => row.assigned_from },
    { key: "to", header: "To", render: (row) => row.assigned_to ?? "—" },
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
        title="Teacher Assignments"
        description="Assign teachers to allocated subject sections."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Assignment
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search assignments..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No teacher assignments found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit assignment for ${teacherName(row.teacher_user_id)}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete assignment for ${teacherName(row.teacher_user_id)}`}
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
        title={editing ? "Edit Teacher Assignment" : "New Teacher Assignment"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="assignment-teacher" label="Teacher" required>
          <Select
            id="assignment-teacher"
            required
            value={form.teacher_user_id}
            onChange={(event) => setForm({ ...form, teacher_user_id: event.target.value })}
          >
            <option value="" disabled>
              Select a teacher
            </option>
            {teachers?.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.full_name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="assignment-allocation" label="Subject Allocation" required>
          <Select
            id="assignment-allocation"
            required
            value={form.subject_allocation_id}
            onChange={(event) => setForm({ ...form, subject_allocation_id: event.target.value })}
          >
            <option value="" disabled>
              Select a subject allocation
            </option>
            {allocations?.map((allocation) => (
              <option key={allocation.id} value={allocation.id}>
                {allocation.id}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="assignment-role" label="Role" required>
          <Select
            id="assignment-role"
            required
            value={form.assignment_role}
            onChange={(event) =>
              setForm({ ...form, assignment_role: event.target.value as AssignmentRole })
            }
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="assignment-from" label="Assigned From" required>
          <Input
            id="assignment-from"
            type="date"
            required
            value={form.assigned_from}
            onChange={(event) => setForm({ ...form, assigned_from: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="assignment-to" label="Assigned To">
          <Input
            id="assignment-to"
            type="date"
            value={form.assigned_to ?? ""}
            onChange={(event) => setForm({ ...form, assigned_to: event.target.value || null })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete teacher assignment?"
        description="This assignment will be soft-deleted and can be restored later."
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
