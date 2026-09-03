import { useMemo, useState, type FormEvent } from "react";
import { FileText, Pencil, Plus, Trash2 } from "lucide-react";

import { assessmentsApi } from "@/api/assessments";
import { examInstructionsApi } from "@/api/examInstructions";
import { examsApi } from "@/api/exams";
import { sectionsApi } from "@/api/sections";
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
import type {
  Exam,
  ExamCreate,
  ExamInstructions,
  ExamInstructionsCreate,
} from "@/types/assessment";

const emptyForm: ExamCreate = { assessment_id: "", section_id: "", name: "", exam_date: "" };

function emptyInstructionForm(examId: string): ExamInstructionsCreate {
  return { exam_id: examId, instructions_text: "", display_order: 0 };
}

/**
 * Master CRUD grid over `Exam`, plus a nested `ExamInstructions` panel scoped
 * to a selected exam (see the Module 04 style guide's nested/child-resource
 * pattern) — instructions have no dedicated screen of their own, so they're
 * managed here rather than via a separate route.
 */
export function ExamManagementPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("exams:create");
  const canUpdate = permissions.includes("exams:update");
  const canDelete = permissions.includes("exams:delete");
  const canCreateInstruction = permissions.includes("exam_instructions:create");
  const canUpdateInstruction = permissions.includes("exam_instructions:update");
  const canDeleteInstruction = permissions.includes("exam_instructions:delete");

  const list = usePaginatedList<Exam>({
    queryKey: "exams",
    fetcher: (params) => examsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "exams",
    examsApi,
    "Exam",
  );
  const { data: assessments } = useSelectOptions("assessments", () =>
    assessmentsApi.list({ page_size: 200 }),
  );
  const { data: sections } = useSelectOptions("sections", () => sectionsApi.list({ page_size: 200 }));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Exam | null>(null);
  const [form, setForm] = useState<ExamCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Exam | null>(null);
  const [selectedExam, setSelectedExam] = useState<Exam | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(exam: Exam) {
    setEditing(exam);
    setForm({
      assessment_id: exam.assessment_id,
      section_id: exam.section_id,
      name: exam.name,
      exam_date: exam.exam_date,
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

  const assessmentName = (id: string) => assessments?.find((a) => a.id === id)?.name ?? id;
  const sectionName = (id: string) => sections?.find((s) => s.id === id)?.name ?? id;

  const columns: Column<Exam>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "assessment", header: "Assessment", render: (row) => assessmentName(row.assessment_id) },
    { key: "section", header: "Section", render: (row) => sectionName(row.section_id) },
    { key: "exam_date", header: "Exam Date", render: (row) => row.exam_date },
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

  // --- Nested exam-instructions panel -------------------------------------

  const instructionsList = usePaginatedList<ExamInstructions>({
    queryKey: "exam-instructions",
    fetcher: (params) => examInstructionsApi.list(params),
    defaultPageSize: 200,
  });
  const instructions = useMemo(
    () => instructionsList.items.filter((row) => row.exam_id === selectedExam?.id),
    [instructionsList.items, selectedExam],
  );
  const {
    createMutation: createInstructionMutation,
    updateMutation: updateInstructionMutation,
    removeMutation: removeInstructionMutation,
  } = useCrudMutations("exam-instructions", examInstructionsApi, "Instruction");

  const [instructionFormOpen, setInstructionFormOpen] = useState(false);
  const [editingInstruction, setEditingInstruction] = useState<ExamInstructions | null>(null);
  const [instructionForm, setInstructionForm] = useState<ExamInstructionsCreate>(
    emptyInstructionForm(""),
  );
  const [deletingInstruction, setDeletingInstruction] = useState<ExamInstructions | null>(null);

  function openCreateInstruction() {
    if (!selectedExam) return;
    setEditingInstruction(null);
    setInstructionForm(emptyInstructionForm(selectedExam.id));
    setInstructionFormOpen(true);
  }

  function openEditInstruction(instruction: ExamInstructions) {
    setEditingInstruction(instruction);
    setInstructionForm({
      exam_id: instruction.exam_id,
      instructions_text: instruction.instructions_text,
      display_order: instruction.display_order,
    });
    setInstructionFormOpen(true);
  }

  function handleInstructionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingInstruction) {
      updateInstructionMutation.mutate(
        { id: editingInstruction.id, data: instructionForm },
        { onSuccess: () => setInstructionFormOpen(false) },
      );
    } else {
      createInstructionMutation.mutate(instructionForm, {
        onSuccess: () => setInstructionFormOpen(false),
      });
    }
  }

  const instructionColumns: Column<ExamInstructions>[] = [
    { key: "display_order", header: "Order", render: (row) => row.display_order },
    { key: "instructions_text", header: "Instructions", render: (row) => row.instructions_text },
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
        title="Exam Management"
        description="Manage exams and their per-exam instructions."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Exam
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search exams..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No exams found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Manage instructions for ${row.name}`}
              onClick={() => setSelectedExam(row)}
            >
              <FileText className="h-4 w-4" />
            </Button>
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
        title={editing ? "Edit Exam" : "New Exam"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="exam-assessment" label="Assessment" required>
          <Select
            id="exam-assessment"
            required
            value={form.assessment_id}
            onChange={(event) => setForm({ ...form, assessment_id: event.target.value })}
          >
            <option value="" disabled>
              Select an assessment
            </option>
            {assessments?.map((assessment) => (
              <option key={assessment.id} value={assessment.id}>
                {assessment.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="exam-section" label="Section" required>
          <Select
            id="exam-section"
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
        <FormField htmlFor="exam-name" label="Name" required>
          <Input
            id="exam-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="exam-date" label="Exam Date" required>
          <Input
            id="exam-date"
            type="date"
            required
            value={form.exam_date}
            onChange={(event) => setForm({ ...form, exam_date: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete exam?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />

      {selectedExam && (
        <div className="mt-8 border-t border-border pt-6">
          <PageHeader
            title={`Instructions for "${selectedExam.name}"`}
            description="Instructions shown to candidates for this exam."
            actions={
              <div className="flex items-center gap-2">
                {canCreateInstruction && (
                  <Button onClick={openCreateInstruction}>
                    <Plus className="h-4 w-4" />
                    New Instruction
                  </Button>
                )}
                <Button variant="outline" onClick={() => setSelectedExam(null)}>
                  Back to exams
                </Button>
              </div>
            }
          />

          <DataTable
            columns={instructionColumns}
            rows={instructions}
            getRowId={(row) => row.id}
            isLoading={instructionsList.isLoading}
            isError={instructionsList.isError}
            emptyMessage="No instructions found."
            renderActions={(row) => (
              <div className="flex justify-end gap-1">
                {canUpdateInstruction && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit instruction ${row.display_order}`}
                    onClick={() => openEditInstruction(row)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
                {canDeleteInstruction && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete instruction ${row.display_order}`}
                    onClick={() => setDeletingInstruction(row)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            )}
          />

          <FormDialog
            open={instructionFormOpen}
            onOpenChange={setInstructionFormOpen}
            title={editingInstruction ? "Edit Instruction" : "New Instruction"}
            onSubmit={handleInstructionSubmit}
            isSubmitting={createInstructionMutation.isPending || updateInstructionMutation.isPending}
            submitLabel={editingInstruction ? "Save changes" : "Create"}
          >
            <FormField htmlFor="instruction-text" label="Instructions" required>
              <Textarea
                id="instruction-text"
                required
                value={instructionForm.instructions_text}
                onChange={(event) =>
                  setInstructionForm({ ...instructionForm, instructions_text: event.target.value })
                }
              />
            </FormField>
            <FormField htmlFor="instruction-order" label="Display Order" required>
              <Input
                id="instruction-order"
                type="number"
                required
                value={instructionForm.display_order ?? 0}
                onChange={(event) =>
                  setInstructionForm({
                    ...instructionForm,
                    display_order: Number(event.target.value),
                  })
                }
              />
            </FormField>
          </FormDialog>

          <ConfirmDialog
            open={deletingInstruction !== null}
            onOpenChange={(open) => !open && setDeletingInstruction(null)}
            title="Delete instruction?"
            description="This instruction will be soft-deleted and can be restored later."
            confirmLabel="Delete"
            variant="destructive"
            isConfirming={removeInstructionMutation.isPending}
            onConfirm={() =>
              deletingInstruction &&
              removeInstructionMutation.mutate(deletingInstruction.id, {
                onSuccess: () => setDeletingInstruction(null),
              })
            }
          />
        </div>
      )}
    </div>
  );
}
