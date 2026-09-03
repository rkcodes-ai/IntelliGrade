import { useMemo, useState, type FormEvent } from "react";
import { Layers, Pencil, Plus, Trash2 } from "lucide-react";

import { bloomTaxonomyLevelsApi } from "@/api/bloomTaxonomyLevels";
import { difficultyLevelsApi } from "@/api/difficultyLevels";
import { questionBlueprintSectionsApi } from "@/api/questionBlueprintSections";
import { questionBlueprintsApi } from "@/api/questionBlueprints";
import { questionCategoriesApi } from "@/api/questionCategories";
import { questionTypesApi } from "@/api/questionTypes";
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
import { useCrudMutations } from "@/hooks/useCrudMutations";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { useAppSelector } from "@/store";
import type {
  QuestionBlueprint,
  QuestionBlueprintCreate,
  QuestionBlueprintSection,
  QuestionBlueprintSectionCreate,
} from "@/types/assessment";

const emptyForm: QuestionBlueprintCreate = {
  subject_id: "",
  name: "",
  total_marks: 0,
  total_questions: 0,
};

function emptySectionForm(blueprintId: string): QuestionBlueprintSectionCreate {
  return {
    blueprint_id: blueprintId,
    question_category_id: null,
    difficulty_level_id: null,
    bloom_level_id: null,
    question_type_id: null,
    number_of_questions: 0,
    marks_per_question: 0,
    display_order: 0,
  };
}

/**
 * Master CRUD grid over `QuestionBlueprint`, plus a nested
 * `QuestionBlueprintSection` panel scoped to a selected blueprint (see the
 * Module 04 style guide's nested/child-resource pattern) — sections have no
 * dedicated screen of their own, so they're managed here.
 */
export function BlueprintBuilderPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("question_blueprints:create");
  const canUpdate = permissions.includes("question_blueprints:update");
  const canDelete = permissions.includes("question_blueprints:delete");
  const canCreateSection = permissions.includes("question_blueprint_sections:create");
  const canUpdateSection = permissions.includes("question_blueprint_sections:update");
  const canDeleteSection = permissions.includes("question_blueprint_sections:delete");

  const list = usePaginatedList<QuestionBlueprint>({
    queryKey: "question-blueprints",
    fetcher: (params) => questionBlueprintsApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "question-blueprints",
    questionBlueprintsApi,
    "Blueprint",
  );
  const { data: subjects } = useSelectOptions("subjects", () => subjectsApi.list({ page_size: 200 }));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<QuestionBlueprint | null>(null);
  const [form, setForm] = useState<QuestionBlueprintCreate>(emptyForm);
  const [deleting, setDeleting] = useState<QuestionBlueprint | null>(null);
  const [selectedBlueprint, setSelectedBlueprint] = useState<QuestionBlueprint | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(blueprint: QuestionBlueprint) {
    setEditing(blueprint);
    setForm({
      subject_id: blueprint.subject_id,
      name: blueprint.name,
      total_marks: Number(blueprint.total_marks),
      total_questions: blueprint.total_questions,
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

  const columns: Column<QuestionBlueprint>[] = [
    { key: "name", header: "Name", render: (row) => row.name },
    { key: "subject", header: "Subject", render: (row) => subjectName(row.subject_id) },
    { key: "total_marks", header: "Total Marks", render: (row) => row.total_marks },
    { key: "total_questions", header: "Total Questions", render: (row) => row.total_questions },
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

  // --- Nested blueprint-sections panel -------------------------------------

  const sectionsList = usePaginatedList<QuestionBlueprintSection>({
    queryKey: "question-blueprint-sections",
    fetcher: (params) => questionBlueprintSectionsApi.list(params),
    defaultPageSize: 200,
  });
  const sections = useMemo(
    () => sectionsList.items.filter((row) => row.blueprint_id === selectedBlueprint?.id),
    [sectionsList.items, selectedBlueprint],
  );
  const {
    createMutation: createSectionMutation,
    updateMutation: updateSectionMutation,
    removeMutation: removeSectionMutation,
  } = useCrudMutations("question-blueprint-sections", questionBlueprintSectionsApi, "Section");

  const { data: categories } = useSelectOptions("question-categories", () =>
    questionCategoriesApi.list({ page_size: 200 }),
  );
  const { data: difficultyLevels } = useSelectOptions("difficulty-levels", () =>
    difficultyLevelsApi.list({ page_size: 200 }),
  );
  const { data: bloomLevels } = useSelectOptions("bloom-taxonomy-levels", () =>
    bloomTaxonomyLevelsApi.list({ page_size: 200 }),
  );
  const { data: questionTypes } = useSelectOptions("question-types", () =>
    questionTypesApi.list({ page_size: 200 }),
  );

  const [sectionFormOpen, setSectionFormOpen] = useState(false);
  const [editingSection, setEditingSection] = useState<QuestionBlueprintSection | null>(null);
  const [sectionForm, setSectionForm] = useState<QuestionBlueprintSectionCreate>(emptySectionForm(""));
  const [deletingSection, setDeletingSection] = useState<QuestionBlueprintSection | null>(null);

  function openCreateSection() {
    if (!selectedBlueprint) return;
    setEditingSection(null);
    setSectionForm(emptySectionForm(selectedBlueprint.id));
    setSectionFormOpen(true);
  }

  function openEditSection(section: QuestionBlueprintSection) {
    setEditingSection(section);
    setSectionForm({
      blueprint_id: section.blueprint_id,
      question_category_id: section.question_category_id,
      difficulty_level_id: section.difficulty_level_id,
      bloom_level_id: section.bloom_level_id,
      question_type_id: section.question_type_id,
      number_of_questions: section.number_of_questions,
      marks_per_question: Number(section.marks_per_question),
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

  const categoryName = (id: string | null) =>
    id ? (categories?.find((c) => c.id === id)?.name ?? id) : "Any";
  const difficultyName = (id: string | null) =>
    id ? (difficultyLevels?.find((d) => d.id === id)?.name ?? id) : "Any";
  const bloomName = (id: string | null) =>
    id ? (bloomLevels?.find((b) => b.id === id)?.name ?? id) : "Any";
  const questionTypeName = (id: string | null) =>
    id ? (questionTypes?.find((t) => t.id === id)?.name ?? id) : "Any";

  const sectionColumns: Column<QuestionBlueprintSection>[] = [
    { key: "category", header: "Category", render: (row) => categoryName(row.question_category_id) },
    { key: "difficulty", header: "Difficulty", render: (row) => difficultyName(row.difficulty_level_id) },
    { key: "bloom", header: "Bloom Level", render: (row) => bloomName(row.bloom_level_id) },
    { key: "question_type", header: "Question Type", render: (row) => questionTypeName(row.question_type_id) },
    { key: "number_of_questions", header: "# Questions", render: (row) => row.number_of_questions },
    { key: "marks_per_question", header: "Marks/Question", render: (row) => row.marks_per_question },
    { key: "display_order", header: "Order", render: (row) => row.display_order },
  ];

  return (
    <div>
      <PageHeader
        title="Blueprint Builder"
        description="Manage question blueprints and their per-blueprint sections."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Blueprint
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search blueprints..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No blueprints found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Manage sections for ${row.name}`}
              onClick={() => setSelectedBlueprint(row)}
            >
              <Layers className="h-4 w-4" />
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
        title={editing ? "Edit Blueprint" : "New Blueprint"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="blueprint-subject" label="Subject" required>
          <Select
            id="blueprint-subject"
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
        <FormField htmlFor="blueprint-name" label="Name" required>
          <Input
            id="blueprint-name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="blueprint-total-marks" label="Total Marks" required>
          <Input
            id="blueprint-total-marks"
            type="number"
            step="0.01"
            required
            value={form.total_marks}
            onChange={(event) => setForm({ ...form, total_marks: Number(event.target.value) })}
          />
        </FormField>
        <FormField htmlFor="blueprint-total-questions" label="Total Questions" required>
          <Input
            id="blueprint-total-questions"
            type="number"
            required
            value={form.total_questions}
            onChange={(event) => setForm({ ...form, total_questions: Number(event.target.value) })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete blueprint?"
        description={`"${deleting?.name}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />

      {selectedBlueprint && (
        <div className="mt-8 border-t border-border pt-6">
          <PageHeader
            title={`Sections for "${selectedBlueprint.name}"`}
            description="Sections define how many questions of each category/difficulty/type this blueprint requires."
            actions={
              <div className="flex items-center gap-2">
                {canCreateSection && (
                  <Button onClick={openCreateSection}>
                    <Plus className="h-4 w-4" />
                    New Section
                  </Button>
                )}
                <Button variant="outline" onClick={() => setSelectedBlueprint(null)}>
                  Back to blueprints
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
                {canUpdateSection && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit section ${row.display_order}`}
                    onClick={() => openEditSection(row)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
                {canDeleteSection && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete section ${row.display_order}`}
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
            <FormField htmlFor="section-category" label="Category">
              <Select
                id="section-category"
                value={sectionForm.question_category_id ?? ""}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    question_category_id: event.target.value || null,
                  })
                }
              >
                <option value="">Any</option>
                {categories?.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField htmlFor="section-difficulty" label="Difficulty">
              <Select
                id="section-difficulty"
                value={sectionForm.difficulty_level_id ?? ""}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    difficulty_level_id: event.target.value || null,
                  })
                }
              >
                <option value="">Any</option>
                {difficultyLevels?.map((difficulty) => (
                  <option key={difficulty.id} value={difficulty.id}>
                    {difficulty.name}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField htmlFor="section-bloom" label="Bloom Level">
              <Select
                id="section-bloom"
                value={sectionForm.bloom_level_id ?? ""}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    bloom_level_id: event.target.value || null,
                  })
                }
              >
                <option value="">Any</option>
                {bloomLevels?.map((bloom) => (
                  <option key={bloom.id} value={bloom.id}>
                    {bloom.name}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField htmlFor="section-question-type" label="Question Type">
              <Select
                id="section-question-type"
                value={sectionForm.question_type_id ?? ""}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    question_type_id: event.target.value || null,
                  })
                }
              >
                <option value="">Any</option>
                {questionTypes?.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField htmlFor="section-number-of-questions" label="# Questions" required>
              <Input
                id="section-number-of-questions"
                type="number"
                required
                value={sectionForm.number_of_questions}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    number_of_questions: Number(event.target.value),
                  })
                }
              />
            </FormField>
            <FormField htmlFor="section-marks-per-question" label="Marks/Question" required>
              <Input
                id="section-marks-per-question"
                type="number"
                step="0.01"
                required
                value={sectionForm.marks_per_question}
                onChange={(event) =>
                  setSectionForm({
                    ...sectionForm,
                    marks_per_question: Number(event.target.value),
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
                  setSectionForm({
                    ...sectionForm,
                    display_order: Number(event.target.value),
                  })
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
    </div>
  );
}
