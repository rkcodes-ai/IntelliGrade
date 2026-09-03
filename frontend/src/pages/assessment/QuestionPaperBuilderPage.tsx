import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Layers, Pencil, Plus, Shuffle, Trash2 } from "lucide-react";

import { assessmentsApi } from "@/api/assessments";
import { questionBlueprintsApi } from "@/api/questionBlueprints";
import {
  approveQuestionPaper,
  createQuestionPaperVersionSnapshot,
  questionPapersApi,
  rejectQuestionPaper,
  submitQuestionPaperForReview,
} from "@/api/questionPapers";
import { questionPaperQuestionMappingsApi } from "@/api/questionPaperQuestionMappings";
import { questionPaperSectionsApi } from "@/api/questionPaperSections";
import { questionPaperTemplatesApi } from "@/api/questionPaperTemplates";
import { questionsApi } from "@/api/questions";
import { randomizationStrategiesApi } from "@/api/randomizationStrategies";
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
import { useToast } from "@/context/ToastProvider";
import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { extractErrorMessage } from "@/lib/errors";
import { useAppSelector } from "@/store";
import type {
  ApprovalStatus,
  QuestionPaper,
  QuestionPaperCreate,
  QuestionPaperQuestionMapping,
  QuestionPaperQuestionMappingCreate,
  QuestionPaperSection,
  QuestionPaperSectionCreate,
  RandomizationStrategyCreate,
  StrategyType,
} from "@/types/assessment";

const emptyForm: QuestionPaperCreate = {
  assessment_id: "",
  blueprint_id: null,
  template_id: null,
  name: "",
  total_marks: 0,
};

function emptySectionForm(questionPaperId: string): QuestionPaperSectionCreate {
  return {
    question_paper_id: questionPaperId,
    name: "",
    instructions: null,
    marks_per_question: null,
    display_order: 0,
  };
}

function emptyMappingForm(sectionId: string): QuestionPaperQuestionMappingCreate {
  return {
    question_paper_section_id: sectionId,
    question_id: "",
    order_index: 0,
    marks_override: null,
    is_optional: false,
  };
}

const STRATEGY_TYPES: StrategyType[] = [
  "none",
  "shuffle_questions",
  "shuffle_options",
  "pick_random_subset",
];

const approvalStatusClassName: Record<ApprovalStatus, string> = {
  draft: "text-muted-foreground",
  pending_review: "text-warning",
  approved: "text-primary",
  rejected: "text-destructive",
  archived: "text-muted-foreground",
};

function truncate(text: string, length = 50) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

/**
 * Master CRUD grid over `QuestionPaper`, plus two levels of nested panels —
 * `QuestionPaperSection` (scoped to a selected paper) and
 * `QuestionPaperQuestionMapping` (scoped to a selected section) — since
 * neither has a dedicated screen of its own (see the Module 04 style guide's
 * nested/child-resource pattern). A minimal randomization-strategy creator
 * also lives inside the papers view rather than as its own nesting level.
 */
export function QuestionPaperBuilderPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("question_papers:create");
  const canUpdate = permissions.includes("question_papers:update");
  const canDelete = permissions.includes("question_papers:delete");
  const canApprove = permissions.includes("question_papers:approve");
  const canReject = permissions.includes("question_papers:reject");
  const canCreateSection = permissions.includes("question_paper_sections:create");
  const canUpdateSection = permissions.includes("question_paper_sections:update");
  const canDeleteSection = permissions.includes("question_paper_sections:delete");
  const canCreateMapping = permissions.includes("question_paper_question_mappings:create");
  const canUpdateMapping = permissions.includes("question_paper_question_mappings:update");
  const canDeleteMapping = permissions.includes("question_paper_question_mappings:delete");

  const { toast } = useToast();
  const queryClient = useQueryClient();

  function invalidatePapers() {
    return queryClient.invalidateQueries({ queryKey: ["question-papers"] });
  }

  const list = usePaginatedList<QuestionPaper>({
    queryKey: "question-papers",
    fetcher: (params) => questionPapersApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "question-papers",
    questionPapersApi,
    "Question paper",
  );
  const { data: assessments } = useSelectOptions("assessments", () =>
    assessmentsApi.list({ page_size: 200 }),
  );
  const { data: blueprints } = useSelectOptions("question-blueprints", () =>
    questionBlueprintsApi.list({ page_size: 200 }),
  );
  const { data: templates } = useSelectOptions("question-paper-templates", () =>
    questionPaperTemplatesApi.list({ page_size: 200 }),
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<QuestionPaper | null>(null);
  const [form, setForm] = useState<QuestionPaperCreate>(emptyForm);
  const [deleting, setDeleting] = useState<QuestionPaper | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<QuestionPaper | null>(null);
  const [selectedSection, setSelectedSection] = useState<QuestionPaperSection | null>(null);

  const [rejecting, setRejecting] = useState<QuestionPaper | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [snapshotting, setSnapshotting] = useState<QuestionPaper | null>(null);
  const [changeReason, setChangeReason] = useState("");
  const [randomizing, setRandomizing] = useState<QuestionPaper | null>(null);
  const [strategyType, setStrategyType] = useState<StrategyType>("none");

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(paper: QuestionPaper) {
    setEditing(paper);
    setForm({
      assessment_id: paper.assessment_id,
      blueprint_id: paper.blueprint_id,
      template_id: paper.template_id,
      name: paper.name,
      total_marks: Number(paper.total_marks),
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

  const submitMutation = useMutation({
    mutationFn: (id: string) => submitQuestionPaperForReview(id),
    onSuccess: () => {
      toast("Question paper submitted for review.", "success");
      void invalidatePapers();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => approveQuestionPaper(id),
    onSuccess: () => {
      toast("Question paper approved.", "success");
      void invalidatePapers();
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectQuestionPaper(id, { reason }),
    onSuccess: () => {
      toast("Question paper rejected.", "success");
      void invalidatePapers();
      setRejecting(null);
      setRejectReason("");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const snapshotMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      createQuestionPaperVersionSnapshot(id, { change_reason: reason || null }),
    onSuccess: () => {
      toast("Version snapshot created.", "success");
      void invalidatePapers();
      setSnapshotting(null);
      setChangeReason("");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const randomizationMutation = useMutation({
    mutationFn: (data: RandomizationStrategyCreate) => randomizationStrategiesApi.create(data),
    onSuccess: () => {
      toast("Randomization strategy created.", "success");
      setRandomizing(null);
      setStrategyType("none");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openReject(paper: QuestionPaper) {
    setRejecting(paper);
    setRejectReason("");
  }

  function handleRejectSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (rejecting) {
      rejectMutation.mutate({ id: rejecting.id, reason: rejectReason });
    }
  }

  function openSnapshot(paper: QuestionPaper) {
    setSnapshotting(paper);
    setChangeReason("");
  }

  function handleSnapshotSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (snapshotting) {
      snapshotMutation.mutate({ id: snapshotting.id, reason: changeReason });
    }
  }

  function openRandomization(paper: QuestionPaper) {
    setRandomizing(paper);
    setStrategyType("none");
  }

  function handleRandomizationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (randomizing) {
      randomizationMutation.mutate({
        question_paper_id: randomizing.id,
        strategy_type: strategyType,
      });
    }
  }

  const assessmentName = (id: string) => assessments?.find((a) => a.id === id)?.name ?? id;

  const columns: Column<QuestionPaper>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "assessment", header: "Assessment", render: (row) => assessmentName(row.assessment_id) },
    { key: "total_marks", header: "Total Marks", render: (row) => row.total_marks },
    {
      key: "approval_status",
      header: "Approval Status",
      render: (row) => (
        <span className={approvalStatusClassName[row.approval_status]}>
          {row.approval_status.replace("_", " ")}
        </span>
      ),
    },
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

  // --- Nested question-paper-sections panel --------------------------------

  const sectionsList = usePaginatedList<QuestionPaperSection>({
    queryKey: "question-paper-sections",
    fetcher: (params) => questionPaperSectionsApi.list(params),
    defaultPageSize: 200,
  });
  const sections = useMemo(
    () => sectionsList.items.filter((row) => row.question_paper_id === selectedPaper?.id),
    [sectionsList.items, selectedPaper],
  );
  const {
    createMutation: createSectionMutation,
    updateMutation: updateSectionMutation,
    removeMutation: removeSectionMutation,
  } = useCrudMutations("question-paper-sections", questionPaperSectionsApi, "Section");

  const [sectionFormOpen, setSectionFormOpen] = useState(false);
  const [editingSection, setEditingSection] = useState<QuestionPaperSection | null>(null);
  const [sectionForm, setSectionForm] = useState<QuestionPaperSectionCreate>(emptySectionForm(""));
  const [deletingSection, setDeletingSection] = useState<QuestionPaperSection | null>(null);

  function openCreateSection() {
    if (!selectedPaper) return;
    setEditingSection(null);
    setSectionForm(emptySectionForm(selectedPaper.id));
    setSectionFormOpen(true);
  }

  function openEditSection(section: QuestionPaperSection) {
    setEditingSection(section);
    setSectionForm({
      question_paper_id: section.question_paper_id,
      name: section.name,
      instructions: section.instructions,
      marks_per_question:
        section.marks_per_question !== null ? Number(section.marks_per_question) : null,
      display_order: section.display_order,
    });
    setSectionFormOpen(true);
  }

  function handleSectionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingSection) {
      updateSectionMutation.mutate(
        { id: editingSection.id, data: sectionForm },
        { onSuccess: () => setSectionFormOpen(false) },
      );
    } else {
      createSectionMutation.mutate(sectionForm, { onSuccess: () => setSectionFormOpen(false) });
    }
  }

  const sectionColumns: Column<QuestionPaperSection>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    {
      key: "instructions",
      header: "Instructions",
      render: (row) => (row.instructions ? truncate(row.instructions) : "—"),
    },
    {
      key: "marks_per_question",
      header: "Marks/Question",
      render: (row) => row.marks_per_question ?? "—",
    },
    { key: "display_order", header: "Order", render: (row) => row.display_order },
  ];

  // --- Nested question-paper-question-mappings panel -----------------------

  const mappingsList = usePaginatedList<QuestionPaperQuestionMapping>({
    queryKey: "question-paper-question-mappings",
    fetcher: (params) => questionPaperQuestionMappingsApi.list(params),
    defaultPageSize: 200,
  });
  const mappings = useMemo(
    () => mappingsList.items.filter((row) => row.question_paper_section_id === selectedSection?.id),
    [mappingsList.items, selectedSection],
  );
  const {
    createMutation: createMappingMutation,
    updateMutation: updateMappingMutation,
    removeMutation: removeMappingMutation,
  } = useCrudMutations(
    "question-paper-question-mappings",
    questionPaperQuestionMappingsApi,
    "Question mapping",
  );
  const { data: questions } = useSelectOptions("questions", () =>
    questionsApi.list({ page_size: 200 }),
  );

  const [mappingFormOpen, setMappingFormOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<QuestionPaperQuestionMapping | null>(null);
  const [mappingForm, setMappingForm] = useState<QuestionPaperQuestionMappingCreate>(
    emptyMappingForm(""),
  );
  const [deletingMapping, setDeletingMapping] = useState<QuestionPaperQuestionMapping | null>(null);

  function openCreateMapping() {
    if (!selectedSection) return;
    setEditingMapping(null);
    setMappingForm(emptyMappingForm(selectedSection.id));
    setMappingFormOpen(true);
  }

  function openEditMapping(mapping: QuestionPaperQuestionMapping) {
    setEditingMapping(mapping);
    setMappingForm({
      question_paper_section_id: mapping.question_paper_section_id,
      question_id: mapping.question_id,
      order_index: mapping.order_index,
      marks_override: mapping.marks_override !== null ? Number(mapping.marks_override) : null,
      is_optional: mapping.is_optional,
    });
    setMappingFormOpen(true);
  }

  function handleMappingSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingMapping) {
      updateMappingMutation.mutate(
        { id: editingMapping.id, data: mappingForm },
        { onSuccess: () => setMappingFormOpen(false) },
      );
    } else {
      createMappingMutation.mutate(mappingForm, { onSuccess: () => setMappingFormOpen(false) });
    }
  }

  const questionText = (id: string) => {
    const question = questions?.find((q) => q.id === id);
    return question ? truncate(question.question_text) : id;
  };

  const mappingColumns: Column<QuestionPaperQuestionMapping>[] = [
    { key: "question", header: "Question", render: (row) => questionText(row.question_id) },
    { key: "order_index", header: "Order", render: (row) => row.order_index },
    {
      key: "marks_override",
      header: "Marks Override",
      render: (row) => row.marks_override ?? "—",
    },
    { key: "is_optional", header: "Optional", render: (row) => (row.is_optional ? "Yes" : "No") },
  ];

  return (
    <div>
      <PageHeader
        title="Question Paper Builder"
        description="Manage question papers, their sections, and section question mappings."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Question Paper
            </Button>
          )
        }
      />

      {!selectedPaper && (
        <>
          <div className="mb-4">
            <SearchInput
              value={list.search}
              onChange={list.setSearch}
              placeholder="Search question papers..."
            />
          </div>

          <DataTable
            columns={columns}
            rows={list.items}
            getRowId={(row) => row.id}
            isLoading={list.isLoading}
            isError={list.isError}
            emptyMessage="No question papers found."
            renderActions={(row) => (
              <div className="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Manage sections for ${row.name}`}
                  onClick={() => setSelectedPaper(row)}
                >
                  <Layers className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Randomization for ${row.name}`}
                  onClick={() => openRandomization(row)}
                >
                  <Shuffle className="h-4 w-4" />
                </Button>
                {row.approval_status === "draft" && canUpdate && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => submitMutation.mutate(row.id)}
                  >
                    Submit for Review
                  </Button>
                )}
                {row.approval_status === "pending_review" && canApprove && (
                  <Button variant="ghost" size="sm" onClick={() => approveMutation.mutate(row.id)}>
                    Approve
                  </Button>
                )}
                {row.approval_status === "pending_review" && canReject && (
                  <Button variant="ghost" size="sm" onClick={() => openReject(row)}>
                    Reject
                  </Button>
                )}
                {canUpdate && (
                  <Button variant="ghost" size="sm" onClick={() => openSnapshot(row)}>
                    Version Snapshot
                  </Button>
                )}
                {canUpdate && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit ${row.name}`}
                    onClick={() => openEdit(row)}
                  >
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
        </>
      )}

      <FormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editing ? "Edit Question Paper" : "New Question Paper"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="paper-assessment" label="Assessment" required>
          <Select
            id="paper-assessment"
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
        <FormField htmlFor="paper-blueprint" label="Blueprint">
          <Select
            id="paper-blueprint"
            value={form.blueprint_id ?? ""}
            onChange={(event) =>
              setForm({ ...form, blueprint_id: event.target.value || null })
            }
          >
            <option value="">None</option>
            {blueprints?.map((blueprint) => (
              <option key={blueprint.id} value={blueprint.id}>
                {blueprint.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="paper-template" label="Template">
          <Select
            id="paper-template"
            value={form.template_id ?? ""}
            onChange={(event) =>
              setForm({ ...form, template_id: event.target.value || null })
            }
          >
            <option value="">None</option>
            {templates?.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="paper-name" label="Name" required>
          <Input
            id="paper-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="paper-total-marks" label="Total Marks" required>
          <Input
            id="paper-total-marks"
            type="number"
            step="0.01"
            required
            value={form.total_marks}
            onChange={(event) => setForm({ ...form, total_marks: Number(event.target.value) })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete question paper?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />

      <FormDialog
        open={rejecting !== null}
        onOpenChange={(open) => !open && setRejecting(null)}
        title="Reject question paper"
        onSubmit={handleRejectSubmit}
        isSubmitting={rejectMutation.isPending}
        submitLabel="Reject"
      >
        <FormField htmlFor="reject-reason" label="Reason" required>
          <Textarea
            id="reject-reason"
            required
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
          />
        </FormField>
      </FormDialog>

      <FormDialog
        open={snapshotting !== null}
        onOpenChange={(open) => !open && setSnapshotting(null)}
        title="Create version snapshot"
        onSubmit={handleSnapshotSubmit}
        isSubmitting={snapshotMutation.isPending}
        submitLabel="Create Snapshot"
      >
        <FormField htmlFor="snapshot-change-reason" label="Change Reason">
          <Textarea
            id="snapshot-change-reason"
            value={changeReason}
            onChange={(event) => setChangeReason(event.target.value)}
          />
        </FormField>
      </FormDialog>

      <FormDialog
        open={randomizing !== null}
        onOpenChange={(open) => !open && setRandomizing(null)}
        title="Randomization Strategy"
        description={randomizing ? `For "${randomizing.name}"` : undefined}
        onSubmit={handleRandomizationSubmit}
        isSubmitting={randomizationMutation.isPending}
        submitLabel="Create"
      >
        <FormField htmlFor="randomization-strategy-type" label="Strategy Type" required>
          <Select
            id="randomization-strategy-type"
            required
            value={strategyType}
            onChange={(event) => setStrategyType(event.target.value as StrategyType)}
          >
            {STRATEGY_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </Select>
        </FormField>
      </FormDialog>

      {selectedPaper && !selectedSection && (
        <div className="mt-8 border-t border-border pt-6">
          <PageHeader
            title={`Sections for "${selectedPaper.name}"`}
            description="Sections group the questions within this question paper."
            actions={
              <div className="flex items-center gap-2">
                {canCreateSection && (
                  <Button onClick={openCreateSection}>
                    <Plus className="h-4 w-4" />
                    New Section
                  </Button>
                )}
                <Button variant="outline" onClick={() => setSelectedPaper(null)}>
                  Back to papers
                </Button>
              </div>
            }
          />

          <DataTable
            columns={sectionColumns}
            rows={sections}
            getRowId={(row) => row.id}
            isLoading={sectionsList.isLoading}
            isError={sectionsList.isError}
            emptyMessage="No sections found."
            renderActions={(row) => (
              <div className="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Manage questions for ${row.name}`}
                  onClick={() => setSelectedSection(row)}
                >
                  <ClipboardList className="h-4 w-4" />
                </Button>
                {canUpdateSection && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit section ${row.name}`}
                    onClick={() => openEditSection(row)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
                {canDeleteSection && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete section ${row.name}`}
                    onClick={() => setDeletingSection(row)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            )}
          />

          <FormDialog
            open={sectionFormOpen}
            onOpenChange={setSectionFormOpen}
            title={editingSection ? "Edit Section" : "New Section"}
            onSubmit={handleSectionSubmit}
            isSubmitting={createSectionMutation.isPending || updateSectionMutation.isPending}
            submitLabel={editingSection ? "Save changes" : "Create"}
          >
            <FormField htmlFor="section-name" label="Name" required>
              <Input
                id="section-name"
                required
                value={sectionForm.name}
                onChange={(event) => setSectionForm({ ...sectionForm, name: event.target.value })}
              />
            </FormField>
            <FormField htmlFor="section-instructions" label="Instructions">
              <Textarea
                id="section-instructions"
                value={sectionForm.instructions ?? ""}
                onChange={(event) =>
                  setSectionForm({ ...sectionForm, instructions: event.target.value || null })
                }
              />
            </FormField>
            <FormField htmlFor="section-marks-per-question" label="Marks/Question">
              <Input
                id="section-marks-per-question"
                type="number"
                step="0.01"
                value={sectionForm.marks_per_question ?? ""}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    marks_per_question: event.target.value === "" ? null : Number(event.target.value),
                  })
                }
              />
            </FormField>
            <FormField htmlFor="section-display-order" label="Display Order" required>
              <Input
                id="section-display-order"
                type="number"
                required
                value={sectionForm.display_order ?? 0}
                onChange={(event) =>
                  setSectionForm({ ...sectionForm, display_order: Number(event.target.value) })
                }
              />
            </FormField>
          </FormDialog>

          <ConfirmDialog
            open={deletingSection !== null}
            onOpenChange={(open) => !open && setDeletingSection(null)}
            title="Delete section?"
            description="This section will be soft-deleted and can be restored later."
            confirmLabel="Delete"
            variant="destructive"
            isConfirming={removeSectionMutation.isPending}
            onConfirm={() =>
              deletingSection &&
              removeSectionMutation.mutate(deletingSection.id, {
                onSuccess: () => setDeletingSection(null),
              })
            }
          />
        </div>
      )}

      {selectedPaper && selectedSection && (
        <div className="mt-8 border-t border-border pt-6">
          <PageHeader
            title={`Questions in "${selectedSection.name}"`}
            description="Questions mapped into this section, in display order."
            actions={
              <div className="flex items-center gap-2">
                {canCreateMapping && (
                  <Button onClick={openCreateMapping}>
                    <Plus className="h-4 w-4" />
                    New Mapping
                  </Button>
                )}
                <Button variant="outline" onClick={() => setSelectedSection(null)}>
                  Back to sections
                </Button>
              </div>
            }
          />

          <DataTable
            columns={mappingColumns}
            rows={mappings}
            getRowId={(row) => row.id}
            isLoading={mappingsList.isLoading}
            isError={mappingsList.isError}
            emptyMessage="No question mappings found."
            renderActions={(row) => (
              <div className="flex justify-end gap-1">
                {canUpdateMapping && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit mapping ${row.order_index}`}
                    onClick={() => openEditMapping(row)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
                {canDeleteMapping && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete mapping ${row.order_index}`}
                    onClick={() => setDeletingMapping(row)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            )}
          />

          <FormDialog
            open={mappingFormOpen}
            onOpenChange={setMappingFormOpen}
            title={editingMapping ? "Edit Mapping" : "New Mapping"}
            onSubmit={handleMappingSubmit}
            isSubmitting={createMappingMutation.isPending || updateMappingMutation.isPending}
            submitLabel={editingMapping ? "Save changes" : "Create"}
          >
            <FormField htmlFor="mapping-question" label="Question" required>
              <Select
                id="mapping-question"
                required
                value={mappingForm.question_id}
                onChange={(event) =>
                  setMappingForm({ ...mappingForm, question_id: event.target.value })
                }
              >
                <option value="" disabled>
                  Select a question
                </option>
                {questions?.map((question) => (
                  <option key={question.id} value={question.id}>
                    {truncate(question.question_text)}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField htmlFor="mapping-order-index" label="Order" required>
              <Input
                id="mapping-order-index"
                type="number"
                required
                value={mappingForm.order_index ?? 0}
                onChange={(event) =>
                  setMappingForm({ ...mappingForm, order_index: Number(event.target.value) })
                }
              />
            </FormField>
            <FormField htmlFor="mapping-marks-override" label="Marks Override">
              <Input
                id="mapping-marks-override"
                type="number"
                step="0.01"
                value={mappingForm.marks_override ?? ""}
                onChange={(event) =>
                  setMappingForm({
                    ...mappingForm,
                    marks_override: event.target.value === "" ? null : Number(event.target.value),
                  })
                }
              />
            </FormField>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={mappingForm.is_optional ?? false}
                onChange={(event) =>
                  setMappingForm({ ...mappingForm, is_optional: event.target.checked })
                }
              />
              Optional
            </label>
          </FormDialog>

          <ConfirmDialog
            open={deletingMapping !== null}
            onOpenChange={(open) => !open && setDeletingMapping(null)}
            title="Delete question mapping?"
            description="This mapping will be soft-deleted and can be restored later."
            confirmLabel="Delete"
            variant="destructive"
            isConfirming={removeMappingMutation.isPending}
            onConfirm={() =>
              deletingMapping &&
              removeMappingMutation.mutate(deletingMapping.id, {
                onSuccess: () => setDeletingMapping(null),
              })
            }
          />
        </div>
      )}
    </div>
  );
}
