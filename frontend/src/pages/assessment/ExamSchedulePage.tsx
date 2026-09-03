import { useState, type FormEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { examSchedulesApi } from "@/api/examSchedules";
import { examsApi } from "@/api/exams";
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
import type { ExamSchedule, ExamScheduleCreate } from "@/types/assessment";

const emptyForm: ExamScheduleCreate = {
  exam_id: "",
  room_id: "",
  start_time: "",
  end_time: "",
  invigilator_user_id: "",
};

/** ISO string -> value `<input type="datetime-local">` expects, e.g. "2026-07-17T09:00". */
function toLocalInputValue(isoValue: string): string {
  return isoValue ? isoValue.slice(0, 16) : "";
}

/** `<input type="datetime-local">` value -> full ISO string for the API payload. */
function toIsoValue(localValue: string): string {
  return localValue ? new Date(localValue).toISOString() : "";
}

export function ExamSchedulePage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("exam_schedules:create");
  const canUpdate = permissions.includes("exam_schedules:update");
  const canDelete = permissions.includes("exam_schedules:delete");

  const list = usePaginatedList<ExamSchedule>({
    queryKey: "exam-schedules",
    fetcher: (params) => examSchedulesApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "exam-schedules",
    examSchedulesApi,
    "Exam schedule",
  );
  const { data: exams } = useSelectOptions("exams", () => examsApi.list({ page_size: 200 }));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ExamSchedule | null>(null);
  const [form, setForm] = useState<ExamScheduleCreate>(emptyForm);
  const [deleting, setDeleting] = useState<ExamSchedule | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(schedule: ExamSchedule) {
    setEditing(schedule);
    setForm({
      exam_id: schedule.exam_id,
      room_id: schedule.room_id ?? "",
      start_time: toLocalInputValue(schedule.start_time),
      end_time: toLocalInputValue(schedule.end_time),
      invigilator_user_id: schedule.invigilator_user_id ?? "",
    });
    setFormOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: ExamScheduleCreate = {
      exam_id: form.exam_id,
      room_id: form.room_id || null,
      start_time: toIsoValue(form.start_time),
      end_time: toIsoValue(form.end_time),
      invigilator_user_id: form.invigilator_user_id || null,
    };
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: payload }, { onSuccess: () => setFormOpen(false) });
    } else {
      createMutation.mutate(payload, { onSuccess: () => setFormOpen(false) });
    }
  }

  const examName = (id: string) => exams?.find((e) => e.id === id)?.name ?? id;

  const columns: Column<ExamSchedule>[] = [
    { key: "exam", header: "Exam", render: (row) => examName(row.exam_id) },
    { key: "room", header: "Room ID", render: (row) => row.room_id ?? "—" },
    { key: "start_time", header: "Start Time", render: (row) => new Date(row.start_time).toLocaleString() },
    { key: "end_time", header: "End Time", render: (row) => new Date(row.end_time).toLocaleString() },
    {
      key: "invigilator",
      header: "Invigilator User ID",
      render: (row) => row.invigilator_user_id ?? "—",
    },
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
        title="Exam Schedule"
        description="Manage exam schedules — room, timing, and invigilator assignments for each exam."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Exam Schedule
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search exam schedules..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No exam schedules found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit ${examName(row.exam_id)}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${examName(row.exam_id)}`}
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
        title={editing ? "Edit Exam Schedule" : "New Exam Schedule"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="exam-schedule-exam" label="Exam" required>
          <Select
            id="exam-schedule-exam"
            required
            value={form.exam_id}
            onChange={(event) => setForm({ ...form, exam_id: event.target.value })}
          >
            <option value="" disabled>
              Select an exam
            </option>
            {exams?.map((exam) => (
              <option key={exam.id} value={exam.id}>
                {exam.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="exam-schedule-room" label="Room ID">
          <Input
            id="exam-schedule-room"
            value={form.room_id ?? ""}
            onChange={(event) => setForm({ ...form, room_id: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="exam-schedule-start" label="Start Time" required>
          <Input
            id="exam-schedule-start"
            type="datetime-local"
            required
            value={form.start_time}
            onChange={(event) => setForm({ ...form, start_time: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="exam-schedule-end" label="End Time" required>
          <Input
            id="exam-schedule-end"
            type="datetime-local"
            required
            value={form.end_time}
            onChange={(event) => setForm({ ...form, end_time: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="exam-schedule-invigilator" label="Invigilator User ID">
          <Input
            id="exam-schedule-invigilator"
            value={form.invigilator_user_id ?? ""}
            onChange={(event) => setForm({ ...form, invigilator_user_id: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete exam schedule?"
        description={`This schedule for "${deleting ? examName(deleting.exam_id) : ""}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
