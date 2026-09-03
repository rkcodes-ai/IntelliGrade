import { useMemo, useState, type FormEvent } from "react";
import { BarChart3, ListTree, Pencil, Plus, Trash2 } from "lucide-react";

import { markDistributionsApi } from "@/api/markDistributions";
import { rubricCriteriaApi } from "@/api/rubricCriteria";
import { rubricsApi } from "@/api/rubrics";
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
import { useAppSelector } from "@/store";
import type {
  MarkDistribution,
  MarkDistributionCreate,
  Rubric,
  RubricCreate,
  RubricCriterion,
  RubricCriterionCreate,
} from "@/types/assessment";

const emptyForm: RubricCreate = { question_id: null, name: "", total_marks: 0 };

function emptyCriterionForm(rubricId: string): RubricCriterionCreate {
  return {
    rubric_id: rubricId,
    parent_criterion_id: null,
    name: "",
    weightage_percent: null,
    max_marks: 0,
    is_mandatory: true,
    teacher_notes: null,
    ai_notes: null,
    display_order: 0,
  };
}

function emptyDistributionForm(criterionId: string): MarkDistributionCreate {
  return {
    rubric_criterion_id: criterionId,
    band_name: "",
    min_score: 0,
    max_score: 0,
    description: null,
  };
}

/**
 * Master CRUD grid over `Rubric`, with two nested levels: `RubricCriterion`
 * scoped to a selected rubric, and `MarkDistribution` scoped to a selected
 * criterion (see the Module 04 style guide's nested/child-resource pattern,
 * extended one level deeper since neither child has a dedicated screen).
 */
export function RubricBuilderPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("rubrics:create");
  const canUpdate = permissions.includes("rubrics:update");
  const canDelete = permissions.includes("rubrics:delete");
  const canCreateCriterion = permissions.includes("rubric_criteria:create");
  const canUpdateCriterion = permissions.includes("rubric_criteria:update");
  const canDeleteCriterion = permissions.includes("rubric_criteria:delete");
  const canCreateDistribution = permissions.includes("mark_distributions:create");
  const canUpdateDistribution = permissions.includes("mark_distributions:update");
  const canDeleteDistribution = permissions.includes("mark_distributions:delete");

  const [view, setView] = useState<"rubrics" | "criteria" | "distributions">("rubrics");
  const [selectedRubric, setSelectedRubric] = useState<Rubric | null>(null);
  const [selectedCriterion, setSelectedCriterion] = useState<RubricCriterion | null>(null);

  function openCriteria(rubric: Rubric) {
    setSelectedRubric(rubric);
    setSelectedCriterion(null);
    setView("criteria");
  }

  function openDistributions(criterion: RubricCriterion) {
    setSelectedCriterion(criterion);
    setView("distributions");
  }

  function backToRubrics() {
    setView("rubrics");
    setSelectedRubric(null);
    setSelectedCriterion(null);
  }

  function backToCriteria() {
    setView("criteria");
    setSelectedCriterion(null);
  }

  // --- Level 1: rubrics -----------------------------------------------------

  const list = usePaginatedList<Rubric>({
    queryKey: "rubrics",
    fetcher: (params) => rubricsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "rubrics",
    rubricsApi,
    "Rubric",
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Rubric | null>(null);
  const [form, setForm] = useState<RubricCreate>(emptyForm);
  const [deleting, setDeleting] = useState<Rubric | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(rubric: Rubric) {
    setEditing(rubric);
    setForm({
      question_id: rubric.question_id,
      name: rubric.name,
      total_marks: Number(rubric.total_marks),
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

  const columns: Column<Rubric>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "question_id", header: "Question ID", render: (row) => row.question_id ?? "Template" },
    { key: "total_marks", header: "Total Marks", render: (row) => row.total_marks },
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

  // --- Level 2: criteria ------------------------------------------------------

  const criteriaList = usePaginatedList<RubricCriterion>({
    queryKey: "rubric-criteria",
    fetcher: (params) => rubricCriteriaApi.list(params),
    defaultPageSize: 200,
  });
  const criteria = useMemo(
    () => criteriaList.items.filter((row) => row.rubric_id === selectedRubric?.id),
    [criteriaList.items, selectedRubric],
  );
  const {
    createMutation: createCriterionMutation,
    updateMutation: updateCriterionMutation,
    removeMutation: removeCriterionMutation,
  } = useCrudMutations("rubric-criteria", rubricCriteriaApi, "Criterion");

  const [criterionFormOpen, setCriterionFormOpen] = useState(false);
  const [editingCriterion, setEditingCriterion] = useState<RubricCriterion | null>(null);
  const [criterionForm, setCriterionForm] = useState<RubricCriterionCreate>(emptyCriterionForm(""));
  const [deletingCriterion, setDeletingCriterion] = useState<RubricCriterion | null>(null);

  function openCreateCriterion() {
    if (!selectedRubric) return;
    setEditingCriterion(null);
    setCriterionForm(emptyCriterionForm(selectedRubric.id));
    setCriterionFormOpen(true);
  }

  function openEditCriterion(criterion: RubricCriterion) {
    setEditingCriterion(criterion);
    setCriterionForm({
      rubric_id: criterion.rubric_id,
      parent_criterion_id: criterion.parent_criterion_id,
      name: criterion.name,
      weightage_percent:
        criterion.weightage_percent === null ? null : Number(criterion.weightage_percent),
      max_marks: Number(criterion.max_marks),
      is_mandatory: criterion.is_mandatory,
      teacher_notes: criterion.teacher_notes,
      ai_notes: criterion.ai_notes,
      display_order: criterion.display_order,
    });
    setCriterionFormOpen(true);
  }

  function handleCriterionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingCriterion) {
      updateCriterionMutation.mutate(
        { id: editingCriterion.id, data: criterionForm },
        { onSuccess: () => setCriterionFormOpen(false) },
      );
    } else {
      createCriterionMutation.mutate(criterionForm, { onSuccess: () => setCriterionFormOpen(false) });
    }
  }

  const parentCriterionOptions = useMemo(
    () => criteria.filter((row) => row.id !== editingCriterion?.id),
    [criteria, editingCriterion],
  );

  const criterionName = (id: string | null) =>
    id ? (criteria.find((row) => row.id === id)?.name ?? "—") : "—";

  const criterionColumns: Column<RubricCriterion>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "parent", header: "Parent", render: (row) => criterionName(row.parent_criterion_id) },
    {
      key: "weightage_percent",
      header: "Weightage %",
      render: (row) => row.weightage_percent ?? "—",
    },
    { key: "max_marks", header: "Max Marks", render: (row) => row.max_marks },
    {
      key: "is_mandatory",
      header: "Mandatory",
      render: (row) => (row.is_mandatory ? "Yes" : "No"),
    },
    { key: "display_order", header: "Order", render: (row) => row.display_order },
  ];

  // --- Level 3: mark distributions ------------------------------------------

  const distributionsList = usePaginatedList<MarkDistribution>({
    queryKey: "mark-distributions",
    fetcher: (params) => markDistributionsApi.list(params),
    defaultPageSize: 200,
  });
  const distributions = useMemo(
    () => distributionsList.items.filter((row) => row.rubric_criterion_id === selectedCriterion?.id),
    [distributionsList.items, selectedCriterion],
  );
  const {
    createMutation: createDistributionMutation,
    updateMutation: updateDistributionMutation,
    removeMutation: removeDistributionMutation,
  } = useCrudMutations("mark-distributions", markDistributionsApi, "Mark band");

  const [distributionFormOpen, setDistributionFormOpen] = useState(false);
  const [editingDistribution, setEditingDistribution] = useState<MarkDistribution | null>(null);
  const [distributionForm, setDistributionForm] = useState<MarkDistributionCreate>(
    emptyDistributionForm(""),
  );
  const [deletingDistribution, setDeletingDistribution] = useState<MarkDistribution | null>(null);

  function openCreateDistribution() {
    if (!selectedCriterion) return;
    setEditingDistribution(null);
    setDistributionForm(emptyDistributionForm(selectedCriterion.id));
    setDistributionFormOpen(true);
  }

  function openEditDistribution(distribution: MarkDistribution) {
    setEditingDistribution(distribution);
    setDistributionForm({
      rubric_criterion_id: distribution.rubric_criterion_id,
      band_name: distribution.band_name,
      min_score: Number(distribution.min_score),
      max_score: Number(distribution.max_score),
      description: distribution.description,
    });
    setDistributionFormOpen(true);
  }

  function handleDistributionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingDistribution) {
      updateDistributionMutation.mutate(
        { id: editingDistribution.id, data: distributionForm },
        { onSuccess: () => setDistributionFormOpen(false) },
      );
    } else {
      createDistributionMutation.mutate(distributionForm, {
        onSuccess: () => setDistributionFormOpen(false),
      });
    }
  }

  const distributionColumns: Column<MarkDistribution>[] = [
    { key: "band_name", header: "Band Name", render: (row) => row.band_name },
    { key: "min_score", header: "Min Score", render: (row) => row.min_score },
    { key: "max_score", header: "Max Score", render: (row) => row.max_score },
    {
      key: "description",
      header: "Description",
      render: (row) =>
        row.description ? (row.description.length > 60 ? `${row.description.slice(0, 60)}...` : row.description) : "—",
    },
  ];

  // --- Render -----------------------------------------------------------------

  if (view === "distributions" && selectedCriterion) {
    return (
      <div>
        <PageHeader
          title={`Mark Bands for "${selectedCriterion.name}"`}
          description="Define the score bands (e.g. Excellent/Good/Poor) evaluators pick from for this criterion."
          actions={
            <div className="flex items-center gap-2">
              {canCreateDistribution && (
                <Button onClick={openCreateDistribution}>
                  <Plus className="h-4 w-4" />
                  New Mark Band
                </Button>
              )}
              <Button variant="outline" onClick={backToCriteria}>
                Back to criteria
              </Button>
            </div>
          }
        />

        <DataTable
          columns={distributionColumns}
          rows={distributions}
          getRowId={(row) => row.id}
          isLoading={distributionsList.isLoading}
          isError={distributionsList.isError}
          emptyMessage="No mark bands found."
          renderActions={(row) => (
            <div className="flex justify-end gap-1">
              {canUpdateDistribution && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Edit ${row.band_name}`}
                  onClick={() => openEditDistribution(row)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
              {canDeleteDistribution && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete ${row.band_name}`}
                  onClick={() => setDeletingDistribution(row)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          )}
        />

        <FormDialog
          open={distributionFormOpen}
          onOpenChange={setDistributionFormOpen}
          title={editingDistribution ? "Edit Mark Band" : "New Mark Band"}
          onSubmit={handleDistributionSubmit}
          isSubmitting={createDistributionMutation.isPending || updateDistributionMutation.isPending}
          submitLabel={editingDistribution ? "Save changes" : "Create"}
        >
          <FormField htmlFor="distribution-band-name" label="Band Name" required>
            <Input
              id="distribution-band-name"
              required
              placeholder="Excellent"
              value={distributionForm.band_name}
              onChange={(event) =>
                setDistributionForm({ ...distributionForm, band_name: event.target.value })
              }
            />
          </FormField>
          <FormField htmlFor="distribution-min-score" label="Min Score" required>
            <Input
              id="distribution-min-score"
              type="number"
              step="0.01"
              required
              value={distributionForm.min_score}
              onChange={(event) =>
                setDistributionForm({ ...distributionForm, min_score: Number(event.target.value) })
              }
            />
          </FormField>
          <FormField htmlFor="distribution-max-score" label="Max Score" required>
            <Input
              id="distribution-max-score"
              type="number"
              step="0.01"
              required
              value={distributionForm.max_score}
              onChange={(event) =>
                setDistributionForm({ ...distributionForm, max_score: Number(event.target.value) })
              }
            />
          </FormField>
          <FormField htmlFor="distribution-description" label="Description">
            <Textarea
              id="distribution-description"
              value={distributionForm.description ?? ""}
              onChange={(event) =>
                setDistributionForm({ ...distributionForm, description: event.target.value || null })
              }
            />
          </FormField>
        </FormDialog>

        <ConfirmDialog
          open={deletingDistribution !== null}
          onOpenChange={(open) => !open && setDeletingDistribution(null)}
          title="Delete mark band?"
          description={`"${deletingDistribution?.band_name}" will be soft-deleted and can be restored later.`}
          confirmLabel="Delete"
          variant="destructive"
          isConfirming={removeDistributionMutation.isPending}
          onConfirm={() =>
            deletingDistribution &&
            removeDistributionMutation.mutate(deletingDistribution.id, {
              onSuccess: () => setDeletingDistribution(null),
            })
          }
        />
      </div>
    );
  }

  if (view === "criteria" && selectedRubric) {
    return (
      <div>
        <PageHeader
          title={`Criteria for "${selectedRubric.name}"`}
          description="Define the scoring criteria that make up this rubric."
          actions={
            <div className="flex items-center gap-2">
              {canCreateCriterion && (
                <Button onClick={openCreateCriterion}>
                  <Plus className="h-4 w-4" />
                  New Criterion
                </Button>
              )}
              <Button variant="outline" onClick={backToRubrics}>
                Back to rubrics
              </Button>
            </div>
          }
        />

        <DataTable
          columns={criterionColumns}
          rows={criteria}
          getRowId={(row) => row.id}
          isLoading={criteriaList.isLoading}
          isError={criteriaList.isError}
          emptyMessage="No criteria found."
          renderActions={(row) => (
            <div className="flex justify-end gap-1">
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Manage mark bands for ${row.name}`}
                onClick={() => openDistributions(row)}
              >
                <BarChart3 className="h-4 w-4" />
              </Button>
              {canUpdateCriterion && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Edit ${row.name}`}
                  onClick={() => openEditCriterion(row)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
              {canDeleteCriterion && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete ${row.name}`}
                  onClick={() => setDeletingCriterion(row)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          )}
        />

        <FormDialog
          open={criterionFormOpen}
          onOpenChange={setCriterionFormOpen}
          title={editingCriterion ? "Edit Criterion" : "New Criterion"}
          onSubmit={handleCriterionSubmit}
          isSubmitting={createCriterionMutation.isPending || updateCriterionMutation.isPending}
          submitLabel={editingCriterion ? "Save changes" : "Create"}
        >
          <FormField htmlFor="criterion-parent" label="Parent Criterion">
            <Select
              id="criterion-parent"
              value={criterionForm.parent_criterion_id ?? ""}
              onChange={(event) =>
                setCriterionForm({
                  ...criterionForm,
                  parent_criterion_id: event.target.value || null,
                })
              }
            >
              <option value="">None (top-level)</option>
              {parentCriterionOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField htmlFor="criterion-name" label="Name" required>
            <Input
              id="criterion-name"
              required
              value={criterionForm.name}
              onChange={(event) => setCriterionForm({ ...criterionForm, name: event.target.value })}
            />
          </FormField>
          <FormField htmlFor="criterion-weightage" label="Weightage %">
            <Input
              id="criterion-weightage"
              type="number"
              step="0.01"
              value={criterionForm.weightage_percent ?? ""}
              onChange={(event) =>
                setCriterionForm({
                  ...criterionForm,
                  weightage_percent: event.target.value === "" ? null : Number(event.target.value),
                })
              }
            />
          </FormField>
          <FormField htmlFor="criterion-max-marks" label="Max Marks" required>
            <Input
              id="criterion-max-marks"
              type="number"
              step="0.01"
              required
              value={criterionForm.max_marks}
              onChange={(event) =>
                setCriterionForm({ ...criterionForm, max_marks: Number(event.target.value) })
              }
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={criterionForm.is_mandatory ?? true}
              onChange={(event) =>
                setCriterionForm({ ...criterionForm, is_mandatory: event.target.checked })
              }
            />
            Mandatory
          </label>
          <FormField htmlFor="criterion-teacher-notes" label="Teacher Notes">
            <Textarea
              id="criterion-teacher-notes"
              value={criterionForm.teacher_notes ?? ""}
              onChange={(event) =>
                setCriterionForm({ ...criterionForm, teacher_notes: event.target.value || null })
              }
            />
          </FormField>
          <FormField
            htmlFor="criterion-ai-notes"
            label="AI Notes (reserved for future AI evaluation — not used by any code yet)"
          >
            <Textarea
              id="criterion-ai-notes"
              value={criterionForm.ai_notes ?? ""}
              onChange={(event) =>
                setCriterionForm({ ...criterionForm, ai_notes: event.target.value || null })
              }
            />
          </FormField>
          <FormField htmlFor="criterion-display-order" label="Display Order" required>
            <Input
              id="criterion-display-order"
              type="number"
              required
              value={criterionForm.display_order ?? 0}
              onChange={(event) =>
                setCriterionForm({ ...criterionForm, display_order: Number(event.target.value) })
              }
            />
          </FormField>
        </FormDialog>

        <ConfirmDialog
          open={deletingCriterion !== null}
          onOpenChange={(open) => !open && setDeletingCriterion(null)}
          title="Delete criterion?"
          description={`"${deletingCriterion?.name}" will be soft-deleted and can be restored later.`}
          confirmLabel="Delete"
          variant="destructive"
          isConfirming={removeCriterionMutation.isPending}
          onConfirm={() =>
            deletingCriterion &&
            removeCriterionMutation.mutate(deletingCriterion.id, {
              onSuccess: () => setDeletingCriterion(null),
            })
          }
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Rubric Builder"
        description="Manage evaluation rubrics, their criteria, and mark bands."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Rubric
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search rubrics..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No rubrics found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Manage criteria for ${row.name}`}
              onClick={() => openCriteria(row)}
            >
              <ListTree className="h-4 w-4" />
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
        title={editing ? "Edit Rubric" : "New Rubric"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField
          htmlFor="rubric-question-id"
          label="Question ID (optional — leave blank for a reusable template)"
        >
          <Input
            id="rubric-question-id"
            value={form.question_id ?? ""}
            onChange={(event) => setForm({ ...form, question_id: event.target.value || null })}
          />
        </FormField>
        <FormField htmlFor="rubric-name" label="Name" required>
          <Input
            id="rubric-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="rubric-total-marks" label="Total Marks" required>
          <Input
            id="rubric-total-marks"
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
        title="Delete rubric?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
