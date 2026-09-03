import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { assessmentStatusesApi } from "@/api/assessmentStatuses";
import { assessmentTypesApi } from "@/api/assessmentTypes";
import { assessmentsApi } from "@/api/assessments";
import { subjectsApi } from "@/api/subjects";
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
import { Textarea } from "@/components/ui/textarea";
import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { useAppSelector } from "@/store";
import type { Assessment, AssessmentCreate } from "@/types/assessment";

const emptyForm: AssessmentCreate = {
  subject_id: "",
  assessment_type_id: "",
  assessment_status_id: "",
  name: "",
  description: "",
};

/**
 * Top-level Assessment Domain landing screen: a CRUD grid over `Assessment`
 * itself (the root entity every Exam/Question Paper hangs off of), with
 * Subject/AssessmentType/AssessmentStatus resolved to labels via
 * `useSelectOptions` exactly like `DepartmentsPage` resolves `campus_id`.
 */
export function AssessmentDashboardPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("assessments:create");
  const canUpdate = permissions.includes("assessments:update");
  const canDelete = permissions.includes("assessments:delete");

  const list = usePaginatedList<Assessment>({
    queryKey: "assessments",
    fetcher: (params) => assessmentsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "assessments",
    assessmentsApi,
    "Assessment",
  );
  const { data: subjects } = useSelectOptions("subjects", () => subjectsApi.list({ page_size: 200 }));
  const { data: types } = useSelectOptions("assessment-types", () =>
    assessmentTypesApi.list({ page_size: 200 }),
  );
  const { data: statuses } = useSelectOptions("assessment-statuses", () =>
    assessmentStatusesApi.list({ page_size: 200 }),
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Assessment | null>(null);
  const [form, setForm] = useState<AssessmentCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Assessment | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(assessment: Assessment) {
    setEditing(assessment);
    setForm({
      subject_id: assessment.subject_id,
      assessment_type_id: assessment.assessment_type_id,
      assessment_status_id: assessment.assessment_status_id,
      name: assessment.name,
      description: assessment.description ?? "",
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

  const subjectName = (id: string) => subjects?.find((s) => s.id === id)?.name ?? id;
  const typeName = (id: string) => types?.find((t) => t.id === id)?.name ?? id;
  const statusName = (id: string) => statuses?.find((s) => s.id === id)?.name ?? id;

  const columns: Column<Assessment>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "subject", header: "Subject", render: (row) => subjectName(row.subject_id) },
    { key: "type", header: "Type", render: (row) => typeName(row.assessment_type_id) },
    { key: "status", header: "Status", render: (row) => statusName(row.assessment_status_id) },
    { key: "version", header: "Version", render: (row) => `v${row.current_version}` },
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
        title="Assessment Dashboard"
        description="Manage assessments — the root entity behind exams, question papers, and question banks."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Assessment
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search assessments..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No assessments found."
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
        title={editing ? "Edit Assessment" : "New Assessment"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="assessment-subject" label="Subject" required>
          <Select
            id="assessment-subject"
            required
            value={form.subject_id}
            onChange={(event) => setForm({ ...form, subject_id: event.target.value })}
          >
            <option value="" disabled>
              Select a subject
            </option>
            {subjects?.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="assessment-type" label="Assessment Type" required>
          <Select
            id="assessment-type"
            required
            value={form.assessment_type_id}
            onChange={(event) => setForm({ ...form, assessment_type_id: event.target.value })}
          >
            <option value="" disabled>
              Select a type
            </option>
            {types?.map((type) => (
              <option key={type.id} value={type.id}>
                {type.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="assessment-status" label="Assessment Status" required>
          <Select
            id="assessment-status"
            required
            value={form.assessment_status_id}
            onChange={(event) => setForm({ ...form, assessment_status_id: event.target.value })}
          >
            <option value="" disabled>
              Select a status
            </option>
            {statuses?.map((status) => (
              <option key={status.id} value={status.id}>
                {status.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="assessment-name" label="Name" required>
          <Input
            id="assessment-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="assessment-description" label="Description">
          <Textarea
            id="assessment-description"
            value={form.description ?? ""}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete assessment?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
