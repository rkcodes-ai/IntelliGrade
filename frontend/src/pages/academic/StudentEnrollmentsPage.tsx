import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { academicYearsApi } from "@/api/academicYears";
import { listAcademicStatuses } from "@/api/academicStatuses";
import { listBatches } from "@/api/batches";
import { coursesApi } from "@/api/courses";
import { sectionsApi } from "@/api/sections";
import { semestersApi } from "@/api/semesters";
import { studentEnrollmentsApi } from "@/api/studentEnrollments";
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
import type { StudentEnrollment, StudentEnrollmentCreate } from "@/types/academic";

const emptyForm: StudentEnrollmentCreate = {
  student_user_id: "",
  batch_id: "",
  section_id: "",
  course_id: "",
  academic_year_id: "",
  semester_id: "",
  academic_status_id: "",
  roll_number: "",
  enrollment_date: "",
};

export function StudentEnrollmentsPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("student_enrollments:create");
  const canUpdate = permissions.includes("student_enrollments:update");
  const canDelete = permissions.includes("student_enrollments:delete");

  const list = usePaginatedList<StudentEnrollment>({
    queryKey: "student-enrollments",
    fetcher: (params) => studentEnrollmentsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "student-enrollments",
    studentEnrollmentsApi,
    "Student Enrollment",
  );

  const { data: batches } = useSelectOptions("batches", () => listBatches({ page_size: 200 }));
  const { data: sections } = useSelectOptions("sections", () => sectionsApi.list({ page_size: 200 }));
  const { data: courses } = useSelectOptions("courses", () => coursesApi.list({ page_size: 200 }));
  const { data: academicYears } = useSelectOptions("academic-years", () =>
    academicYearsApi.list({ page_size: 200 }),
  );
  const { data: semesters } = useSelectOptions("semesters", () => semestersApi.list({ page_size: 200 }));
  const { data: statuses } = useSelectOptions("academic-statuses", () =>
    listAcademicStatuses({ page_size: 200 }),
  );
  const { data: users } = useQuery({
    queryKey: ["users", "students-for-select"],
    queryFn: () => listUsers({ limit: 200 }),
  });
  const students = users?.filter((user) => user.roles.includes("student"));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<StudentEnrollment | null>(null);
  const [form, setForm] = useState<StudentEnrollmentCreate>(emptyForm);
  const [deleting, setDeleting] = useState<StudentEnrollment | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(enrollment: StudentEnrollment) {
    setEditing(enrollment);
    setForm({
      student_user_id: enrollment.student_user_id,
      batch_id: enrollment.batch_id,
      section_id: enrollment.section_id,
      course_id: enrollment.course_id,
      academic_year_id: enrollment.academic_year_id,
      semester_id: enrollment.semester_id,
      academic_status_id: enrollment.academic_status_id,
      roll_number: enrollment.roll_number,
      enrollment_date: enrollment.enrollment_date,
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

  const studentName = (id: string) => students?.find((s) => s.id === id)?.full_name ?? id;
  const statusName = (id: string) => statuses?.find((s) => s.id === id)?.name ?? id;

  const columns: Column<StudentEnrollment>[] = [
    { key: "roll", header: "Roll No.", render: (row) => row.roll_number },
    { key: "student", header: "Student", render: (row) => studentName(row.student_user_id) },
    { key: "status", header: "Status", render: (row) => statusName(row.academic_status_id) },
    { key: "date", header: "Enrolled On", render: (row) => row.enrollment_date },
  ];

  return (
    <div>
      <PageHeader
        title="Student Enrollments"
        description="Manage student enrollments into batches and sections."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Enrollment
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search enrollments..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No student enrollments found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit enrollment ${row.roll_number}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete enrollment ${row.roll_number}`}
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
        title={editing ? "Edit Student Enrollment" : "New Student Enrollment"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="enroll-student" label="Student" required>
          <Select
            id="enroll-student"
            required
            value={form.student_user_id}
            onChange={(event) => setForm({ ...form, student_user_id: event.target.value })}
          >
            <option value="" disabled>
              Select a student
            </option>
            {students?.map((student) => (
              <option key={student.id} value={student.id}>
                {student.full_name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="enroll-course" label="Course" required>
          <Select
            id="enroll-course"
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
        <FormField htmlFor="enroll-batch" label="Batch" required>
          <Select
            id="enroll-batch"
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
        <FormField htmlFor="enroll-section" label="Section" required>
          <Select
            id="enroll-section"
            required
            value={form.section_id}
            onChange={(event) => setForm({ ...form, section_id: event.target.value })}
          >
            <option value="" disabled>
              Select a section
            </option>
            {sections?.map((section) => (
              <option key={section.id} value={section.id}>
                {section.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="enroll-year" label="Academic Year" required>
          <Select
            id="enroll-year"
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
        <FormField htmlFor="enroll-semester" label="Semester" required>
          <Select
            id="enroll-semester"
            required
            value={form.semester_id}
            onChange={(event) => setForm({ ...form, semester_id: event.target.value })}
          >
            <option value="" disabled>
              Select a semester
            </option>
            {semesters?.map((semester) => (
              <option key={semester.id} value={semester.id}>
                {semester.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="enroll-status" label="Academic Status" required>
          <Select
            id="enroll-status"
            required
            value={form.academic_status_id}
            onChange={(event) => setForm({ ...form, academic_status_id: event.target.value })}
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
        <FormField htmlFor="enroll-roll" label="Roll Number" required>
          <Input
            id="enroll-roll"
            required
            value={form.roll_number}
            onChange={(event) => setForm({ ...form, roll_number: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="enroll-date" label="Enrollment Date" required>
          <Input
            id="enroll-date"
            type="date"
            required
            value={form.enrollment_date}
            onChange={(event) => setForm({ ...form, enrollment_date: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete student enrollment?"
        description={`Enrollment "${deleting?.roll_number}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
