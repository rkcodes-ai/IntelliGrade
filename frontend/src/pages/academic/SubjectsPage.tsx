import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { coursesApi } from "@/api/courses";
import { subjectsApi } from "@/api/subjects";
import { listSubjectCategories } from "@/api/subjectCategories";
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
import type { Subject, SubjectCreate } from "@/types/academic";

const emptyForm: SubjectCreate = {
  course_id: "",
  subject_category_id: "",
  code: "",
  name: "",
  credits: 4,
  semester_number: 1,
};

export function SubjectsPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("subjects:create");
  const canUpdate = permissions.includes("subjects:update");
  const canDelete = permissions.includes("subjects:delete");

  const list = usePaginatedList<Subject>({
    queryKey: "subjects",
    fetcher: (params) => subjectsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "subjects",
    subjectsApi,
    "Subject",
  );
  const { data: courses } = useSelectOptions("courses", () => coursesApi.list({ page_size: 200 }));
  const { data: categories } = useSelectOptions("subject-categories", () =>
    listSubjectCategories({ page_size: 200 }),
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Subject | null>(null);
  const [form, setForm] = useState<SubjectCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Subject | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(subject: Subject) {
    setEditing(subject);
    setForm({
      course_id: subject.course_id,
      subject_category_id: subject.subject_category_id,
      code: subject.code,
      name: subject.name,
      credits: Number(subject.credits),
      semester_number: subject.semester_number,
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

  const courseName = (id: string) => courses?.find((c) => c.id === id)?.name ?? id;
  const categoryName = (id: string) => categories?.find((c) => c.id === id)?.name ?? id;

  const columns: Column<Subject>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "code", header: "Code", render: (row) => row.code },
    { key: "course", header: "Course", render: (row) => courseName(row.course_id) },
    { key: "category", header: "Category", render: (row) => categoryName(row.subject_category_id) },
    { key: "credits", header: "Credits", render: (row) => row.credits },
    { key: "semester", header: "Semester #", render: (row) => row.semester_number },
  ];

  return (
    <div>
      <PageHeader
        title="Subjects"
        description="Manage subjects offered under each course."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Subject
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search subjects..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No subjects found."
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
        title={editing ? "Edit Subject" : "New Subject"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="subject-course" label="Course" required>
          <Select
            id="subject-course"
            required
            value={form.course_id}
            onChange={(event) => setForm({ ...form, course_id: event.target.value })}
          >
            <option value="" disabled>
              Select a course
            </option>
            {courses?.map((course) => (
              <option key={course.id} value={course.id}>
                {course.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="subject-category" label="Category" required>
          <Select
            id="subject-category"
            required
            value={form.subject_category_id}
            onChange={(event) => setForm({ ...form, subject_category_id: event.target.value })}
          >
            <option value="" disabled>
              Select a category
            </option>
            {categories?.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="subject-code" label="Code" required>
          <Input
            id="subject-code"
            required
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
        </FormField>
        <FormField htmlFor="subject-name" label="Name" required>
          <Input
            id="subject-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="subject-credits" label="Credits" required>
          <Input
            id="subject-credits"
            type="number"
            min={0.5}
            step={0.5}
            required
            value={form.credits}
            onChange={(event) => setForm({ ...form, credits: Number(event.target.value) })}
          />
        </FormField>
        <FormField htmlFor="subject-semester" label="Semester Number" required>
          <Input
            id="subject-semester"
            type="number"
            min={1}
            max={20}
            required
            value={form.semester_number}
            onChange={(event) => setForm({ ...form, semester_number: Number(event.target.value) })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete subject?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
