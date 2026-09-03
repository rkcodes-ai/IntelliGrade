import { useMemo, useState, type FormEvent } from "react";
import { FileText, Pencil, Plus, Trash2 } from "lucide-react";

import { alternativeAnswersApi } from "@/api/alternativeAnswers";
import { answerKeysApi } from "@/api/answerKeys";
import { expectedConceptsApi } from "@/api/expectedConcepts";
import { expectedKeywordsApi } from "@/api/expectedKeywords";
import { modelAnswersApi } from "@/api/modelAnswers";
import { questionsApi } from "@/api/questions";
import { referenceNotesApi } from "@/api/referenceNotes";
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
  AlternativeAnswer,
  AlternativeAnswerCreate,
  AnswerKey,
  AnswerKeyCreate,
  ExpectedConcept,
  ExpectedConceptCreate,
  ExpectedKeyword,
  ExpectedKeywordCreate,
  ModelAnswer,
  ModelAnswerCreate,
  NoteType,
  ReferenceNote,
  ReferenceNoteCreate,
} from "@/types/assessment";

function truncate(text: string, maxLength: number) {
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

// expected_structure/confidence_threshold/ai_config are AI-preparation
// placeholders per ADR-024 (or complex JSON) — out of scope for this UI.
const emptyForm: AnswerKeyCreate = {
  question_id: "",
  reference_answer: "",
  expected_length: null,
  evaluation_notes: null,
};

function emptyModelAnswerForm(answerKeyId: string): ModelAnswerCreate {
  return { answer_key_id: answerKeyId, content: "", marks_allocated: null, display_order: 0 };
}

function emptyAlternativeAnswerForm(answerKeyId: string): AlternativeAnswerCreate {
  return { answer_key_id: answerKeyId, content: "", is_exact_match: false };
}

function emptyReferenceNoteForm(answerKeyId: string): ReferenceNoteCreate {
  return { answer_key_id: answerKeyId, note_text: "", note_type: "teacher_note" };
}

// rubric_criterion_id deliberately omitted — this screen always creates
// answer-key-scoped keywords, never rubric-criterion-scoped ones.
function emptyExpectedKeywordForm(answerKeyId: string): ExpectedKeywordCreate {
  return { answer_key_id: answerKeyId, keyword: "", weight: null, is_mandatory: false };
}

// rubric_criterion_id deliberately omitted, same reasoning as expected keywords above.
function emptyExpectedConceptForm(answerKeyId: string): ExpectedConceptCreate {
  return { answer_key_id: answerKeyId, concept_name: "", description: null, is_mandatory: false };
}

const noteTypeOptions: { value: NoteType; label: string }[] = [
  { value: "teacher_note", label: "Teacher Note" },
  { value: "ai_note", label: "AI Note" },
];

/**
 * Master CRUD grid over `AnswerKey`, plus a detail view scoped to a selected
 * key holding FOUR nested sub-panels (Model Answers, Alternative Answers,
 * Reference Notes, and combined Expected Keywords/Concepts) — see the
 * Module 04 style guide's nested/child-resource pattern. Unlike Blueprint
 * Builder's single child collection, this screen has five sibling children
 * shown as sub-panels rather than five separate drill-down levels.
 */
export function AnswerKeyBuilderPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCreate = permissions.includes("answer_keys:create");
  const canUpdate = permissions.includes("answer_keys:update");
  const canDelete = permissions.includes("answer_keys:delete");
  const canCreateModelAnswer = permissions.includes("model_answers:create");
  const canUpdateModelAnswer = permissions.includes("model_answers:update");
  const canDeleteModelAnswer = permissions.includes("model_answers:delete");
  const canCreateAlternativeAnswer = permissions.includes("alternative_answers:create");
  const canUpdateAlternativeAnswer = permissions.includes("alternative_answers:update");
  const canDeleteAlternativeAnswer = permissions.includes("alternative_answers:delete");
  const canCreateReferenceNote = permissions.includes("reference_notes:create");
  const canUpdateReferenceNote = permissions.includes("reference_notes:update");
  const canDeleteReferenceNote = permissions.includes("reference_notes:delete");
  const canCreateExpectedKeyword = permissions.includes("expected_keywords:create");
  const canUpdateExpectedKeyword = permissions.includes("expected_keywords:update");
  const canDeleteExpectedKeyword = permissions.includes("expected_keywords:delete");
  const canCreateExpectedConcept = permissions.includes("expected_concepts:create");
  const canUpdateExpectedConcept = permissions.includes("expected_concepts:update");
  const canDeleteExpectedConcept = permissions.includes("expected_concepts:delete");

  const list = usePaginatedList<AnswerKey>({
    queryKey: "answer-keys",
    fetcher: (params) => answerKeysApi.list(params),
  });
  const { createMutation, updateMutation, removeMutation } = useCrudMutations(
    "answer-keys",
    answerKeysApi,
    "Answer Key",
  );
  const { data: questions } = useSelectOptions("questions", () => questionsApi.list({ page_size: 200 }));

  const [view, setView] = useState<"keys" | "detail">("keys");
  const [selectedKey, setSelectedKey] = useState<AnswerKey | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AnswerKey | null>(null);
  const [form, setForm] = useState<AnswerKeyCreate>(emptyForm);
  const [deleting, setDeleting] = useState<AnswerKey | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  }

  function openEdit(key: AnswerKey) {
    setEditing(key);
    setForm({
      question_id: key.question_id,
      reference_answer: key.reference_answer,
      expected_length: key.expected_length,
      evaluation_notes: key.evaluation_notes,
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

  function openDetail(key: AnswerKey) {
    setSelectedKey(key);
    setView("detail");
  }

  function backToKeys() {
    setView("keys");
    setSelectedKey(null);
  }

  const questionLabel = (id: string) => {
    const question = questions?.find((item) => item.id === id);
    return question ? truncate(question.question_text, 50) : id;
  };

  const columns: Column<AnswerKey>[] = [
    { key: "question", header: "Question", render: (row) => questionLabel(row.question_id) },
    {
      key: "reference_answer",
      header: "Reference Answer",
      render: (row) => truncate(row.reference_answer, 60),
    },
    { key: "expected_length", header: "Expected Length", render: (row) => row.expected_length ?? "—" },
    { key: "version", header: "Version", render: (row) => `v${row.current_version}` },
  ];

  // --- Model Answers ---------------------------------------------------------

  const modelAnswersList = usePaginatedList<ModelAnswer>({
    queryKey: "model-answers",
    fetcher: (params) => modelAnswersApi.list(params),
    defaultPageSize: 200,
  });
  const modelAnswers = useMemo(
    () => modelAnswersList.items.filter((row) => row.answer_key_id === selectedKey?.id),
    [modelAnswersList.items, selectedKey],
  );
  const {
    createMutation: createModelAnswerMutation,
    updateMutation: updateModelAnswerMutation,
    removeMutation: removeModelAnswerMutation,
  } = useCrudMutations("model-answers", modelAnswersApi, "Model Answer");

  const [modelAnswerFormOpen, setModelAnswerFormOpen] = useState(false);
  const [editingModelAnswer, setEditingModelAnswer] = useState<ModelAnswer | null>(null);
  const [modelAnswerForm, setModelAnswerForm] = useState<ModelAnswerCreate>(emptyModelAnswerForm(""));
  const [deletingModelAnswer, setDeletingModelAnswer] = useState<ModelAnswer | null>(null);

  function openCreateModelAnswer() {
    if (!selectedKey) return;
    setEditingModelAnswer(null);
    setModelAnswerForm(emptyModelAnswerForm(selectedKey.id));
    setModelAnswerFormOpen(true);
  }

  function openEditModelAnswer(row: ModelAnswer) {
    setEditingModelAnswer(row);
    setModelAnswerForm({
      answer_key_id: row.answer_key_id,
      content: row.content,
      marks_allocated: row.marks_allocated !== null ? Number(row.marks_allocated) : null,
      display_order: row.display_order,
    });
    setModelAnswerFormOpen(true);
  }

  function handleModelAnswerSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingModelAnswer) {
      updateModelAnswerMutation.mutate(
        { id: editingModelAnswer.id, data: modelAnswerForm },
        { onSuccess: () => setModelAnswerFormOpen(false) },
      );
    } else {
      createModelAnswerMutation.mutate(modelAnswerForm, {
        onSuccess: () => setModelAnswerFormOpen(false),
      });
    }
  }

  const modelAnswerColumns: Column<ModelAnswer>[] = [
    { key: "content", header: "Content", render: (row) => truncate(row.content, 60) },
    { key: "marks", header: "Marks", render: (row) => row.marks_allocated ?? "—" },
    { key: "order", header: "Order", render: (row) => row.display_order },
  ];

  // --- Alternative Answers ----------------------------------------------------

  const alternativeAnswersList = usePaginatedList<AlternativeAnswer>({
    queryKey: "alternative-answers",
    fetcher: (params) => alternativeAnswersApi.list(params),
    defaultPageSize: 200,
  });
  const alternativeAnswers = useMemo(
    () => alternativeAnswersList.items.filter((row) => row.answer_key_id === selectedKey?.id),
    [alternativeAnswersList.items, selectedKey],
  );
  const {
    createMutation: createAlternativeAnswerMutation,
    updateMutation: updateAlternativeAnswerMutation,
    removeMutation: removeAlternativeAnswerMutation,
  } = useCrudMutations("alternative-answers", alternativeAnswersApi, "Alternative Answer");

  const [alternativeAnswerFormOpen, setAlternativeAnswerFormOpen] = useState(false);
  const [editingAlternativeAnswer, setEditingAlternativeAnswer] = useState<AlternativeAnswer | null>(null);
  const [alternativeAnswerForm, setAlternativeAnswerForm] = useState<AlternativeAnswerCreate>(
    emptyAlternativeAnswerForm(""),
  );
  const [deletingAlternativeAnswer, setDeletingAlternativeAnswer] = useState<AlternativeAnswer | null>(null);

  function openCreateAlternativeAnswer() {
    if (!selectedKey) return;
    setEditingAlternativeAnswer(null);
    setAlternativeAnswerForm(emptyAlternativeAnswerForm(selectedKey.id));
    setAlternativeAnswerFormOpen(true);
  }

  function openEditAlternativeAnswer(row: AlternativeAnswer) {
    setEditingAlternativeAnswer(row);
    setAlternativeAnswerForm({
      answer_key_id: row.answer_key_id,
      content: row.content,
      is_exact_match: row.is_exact_match,
    });
    setAlternativeAnswerFormOpen(true);
  }

  function handleAlternativeAnswerSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingAlternativeAnswer) {
      updateAlternativeAnswerMutation.mutate(
        { id: editingAlternativeAnswer.id, data: alternativeAnswerForm },
        { onSuccess: () => setAlternativeAnswerFormOpen(false) },
      );
    } else {
      createAlternativeAnswerMutation.mutate(alternativeAnswerForm, {
        onSuccess: () => setAlternativeAnswerFormOpen(false),
      });
    }
  }

  const alternativeAnswerColumns: Column<AlternativeAnswer>[] = [
    { key: "content", header: "Content", render: (row) => truncate(row.content, 60) },
    { key: "exact_match", header: "Exact Match", render: (row) => (row.is_exact_match ? "Yes" : "No") },
  ];

  // --- Reference Notes ---------------------------------------------------------

  const referenceNotesList = usePaginatedList<ReferenceNote>({
    queryKey: "reference-notes",
    fetcher: (params) => referenceNotesApi.list(params),
    defaultPageSize: 200,
  });
  const referenceNotes = useMemo(
    () => referenceNotesList.items.filter((row) => row.answer_key_id === selectedKey?.id),
    [referenceNotesList.items, selectedKey],
  );
  const {
    createMutation: createReferenceNoteMutation,
    updateMutation: updateReferenceNoteMutation,
    removeMutation: removeReferenceNoteMutation,
  } = useCrudMutations("reference-notes", referenceNotesApi, "Reference Note");

  const [referenceNoteFormOpen, setReferenceNoteFormOpen] = useState(false);
  const [editingReferenceNote, setEditingReferenceNote] = useState<ReferenceNote | null>(null);
  const [referenceNoteForm, setReferenceNoteForm] = useState<ReferenceNoteCreate>(
    emptyReferenceNoteForm(""),
  );
  const [deletingReferenceNote, setDeletingReferenceNote] = useState<ReferenceNote | null>(null);

  function openCreateReferenceNote() {
    if (!selectedKey) return;
    setEditingReferenceNote(null);
    setReferenceNoteForm(emptyReferenceNoteForm(selectedKey.id));
    setReferenceNoteFormOpen(true);
  }

  function openEditReferenceNote(row: ReferenceNote) {
    setEditingReferenceNote(row);
    setReferenceNoteForm({
      answer_key_id: row.answer_key_id,
      note_text: row.note_text,
      note_type: row.note_type,
    });
    setReferenceNoteFormOpen(true);
  }

  function handleReferenceNoteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingReferenceNote) {
      updateReferenceNoteMutation.mutate(
        { id: editingReferenceNote.id, data: referenceNoteForm },
        { onSuccess: () => setReferenceNoteFormOpen(false) },
      );
    } else {
      createReferenceNoteMutation.mutate(referenceNoteForm, {
        onSuccess: () => setReferenceNoteFormOpen(false),
      });
    }
  }

  const referenceNoteColumns: Column<ReferenceNote>[] = [
    { key: "note_text", header: "Note", render: (row) => truncate(row.note_text, 60) },
    { key: "note_type", header: "Type", render: (row) => row.note_type },
  ];

  // --- Expected Keywords --------------------------------------------------------

  const expectedKeywordsList = usePaginatedList<ExpectedKeyword>({
    queryKey: "expected-keywords",
    fetcher: (params) => expectedKeywordsApi.list(params),
    defaultPageSize: 200,
  });
  const expectedKeywords = useMemo(
    () => expectedKeywordsList.items.filter((row) => row.answer_key_id === selectedKey?.id),
    [expectedKeywordsList.items, selectedKey],
  );
  const {
    createMutation: createExpectedKeywordMutation,
    updateMutation: updateExpectedKeywordMutation,
    removeMutation: removeExpectedKeywordMutation,
  } = useCrudMutations("expected-keywords", expectedKeywordsApi, "Expected Keyword");

  const [expectedKeywordFormOpen, setExpectedKeywordFormOpen] = useState(false);
  const [editingExpectedKeyword, setEditingExpectedKeyword] = useState<ExpectedKeyword | null>(null);
  const [expectedKeywordForm, setExpectedKeywordForm] = useState<ExpectedKeywordCreate>(
    emptyExpectedKeywordForm(""),
  );
  const [deletingExpectedKeyword, setDeletingExpectedKeyword] = useState<ExpectedKeyword | null>(null);

  function openCreateExpectedKeyword() {
    if (!selectedKey) return;
    setEditingExpectedKeyword(null);
    setExpectedKeywordForm(emptyExpectedKeywordForm(selectedKey.id));
    setExpectedKeywordFormOpen(true);
  }

  function openEditExpectedKeyword(row: ExpectedKeyword) {
    setEditingExpectedKeyword(row);
    setExpectedKeywordForm({
      answer_key_id: row.answer_key_id,
      keyword: row.keyword,
      weight: row.weight !== null ? Number(row.weight) : null,
      is_mandatory: row.is_mandatory,
    });
    setExpectedKeywordFormOpen(true);
  }

  function handleExpectedKeywordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingExpectedKeyword) {
      updateExpectedKeywordMutation.mutate(
        { id: editingExpectedKeyword.id, data: expectedKeywordForm },
        { onSuccess: () => setExpectedKeywordFormOpen(false) },
      );
    } else {
      createExpectedKeywordMutation.mutate(expectedKeywordForm, {
        onSuccess: () => setExpectedKeywordFormOpen(false),
      });
    }
  }

  const expectedKeywordColumns: Column<ExpectedKeyword>[] = [
    { key: "keyword", header: "Keyword", render: (row) => row.keyword },
    { key: "weight", header: "Weight", render: (row) => row.weight ?? "—" },
    { key: "mandatory", header: "Mandatory", render: (row) => (row.is_mandatory ? "Yes" : "No") },
  ];

  // --- Expected Concepts --------------------------------------------------------

  const expectedConceptsList = usePaginatedList<ExpectedConcept>({
    queryKey: "expected-concepts",
    fetcher: (params) => expectedConceptsApi.list(params),
    defaultPageSize: 200,
  });
  const expectedConcepts = useMemo(
    () => expectedConceptsList.items.filter((row) => row.answer_key_id === selectedKey?.id),
    [expectedConceptsList.items, selectedKey],
  );
  const {
    createMutation: createExpectedConceptMutation,
    updateMutation: updateExpectedConceptMutation,
    removeMutation: removeExpectedConceptMutation,
  } = useCrudMutations("expected-concepts", expectedConceptsApi, "Expected Concept");

  const [expectedConceptFormOpen, setExpectedConceptFormOpen] = useState(false);
  const [editingExpectedConcept, setEditingExpectedConcept] = useState<ExpectedConcept | null>(null);
  const [expectedConceptForm, setExpectedConceptForm] = useState<ExpectedConceptCreate>(
    emptyExpectedConceptForm(""),
  );
  const [deletingExpectedConcept, setDeletingExpectedConcept] = useState<ExpectedConcept | null>(null);

  function openCreateExpectedConcept() {
    if (!selectedKey) return;
    setEditingExpectedConcept(null);
    setExpectedConceptForm(emptyExpectedConceptForm(selectedKey.id));
    setExpectedConceptFormOpen(true);
  }

  function openEditExpectedConcept(row: ExpectedConcept) {
    setEditingExpectedConcept(row);
    setExpectedConceptForm({
      answer_key_id: row.answer_key_id,
      concept_name: row.concept_name,
      description: row.description,
      is_mandatory: row.is_mandatory,
    });
    setExpectedConceptFormOpen(true);
  }

  function handleExpectedConceptSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingExpectedConcept) {
      updateExpectedConceptMutation.mutate(
        { id: editingExpectedConcept.id, data: expectedConceptForm },
        { onSuccess: () => setExpectedConceptFormOpen(false) },
      );
    } else {
      createExpectedConceptMutation.mutate(expectedConceptForm, {
        onSuccess: () => setExpectedConceptFormOpen(false),
      });
    }
  }

  const expectedConceptColumns: Column<ExpectedConcept>[] = [
    { key: "concept_name", header: "Concept Name", render: (row) => row.concept_name },
    {
      key: "description",
      header: "Description",
      render: (row) => (row.description ? truncate(row.description, 50) : "—"),
    },
    { key: "mandatory", header: "Mandatory", render: (row) => (row.is_mandatory ? "Yes" : "No") },
  ];

  if (view === "detail" && selectedKey) {
    return (
      <div>
        <PageHeader
          title={`Details for Answer Key on "${questionLabel(selectedKey.question_id)}"`}
          description="Manage this answer key's model answers, alternative answers, reference notes, and expected keywords/concepts."
          actions={
            <Button variant="outline" onClick={backToKeys}>
              Back to answer keys
            </Button>
          }
        />

        <div className="flex flex-col gap-8">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Model Answers</h2>
              {canCreateModelAnswer && (
                <Button size="sm" onClick={openCreateModelAnswer}>
                  <Plus className="h-4 w-4" />
                  Add Model Answer
                </Button>
              )}
            </div>
            <DataTable
              columns={modelAnswerColumns}
              rows={modelAnswers}
              getRowId={(row) => row.id}
              isLoading={modelAnswersList.isLoading}
              isError={modelAnswersList.isError}
              emptyMessage="No model answers found."
              renderActions={(row) => (
                <div className="flex justify-end gap-1">
                  {canUpdateModelAnswer && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit model answer ${row.display_order}`}
                      onClick={() => openEditModelAnswer(row)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  )}
                  {canDeleteModelAnswer && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete model answer ${row.display_order}`}
                      onClick={() => setDeletingModelAnswer(row)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            />
            <FormDialog
              open={modelAnswerFormOpen}
              onOpenChange={setModelAnswerFormOpen}
              title={editingModelAnswer ? "Edit Model Answer" : "New Model Answer"}
              onSubmit={handleModelAnswerSubmit}
              isSubmitting={createModelAnswerMutation.isPending || updateModelAnswerMutation.isPending}
              submitLabel={editingModelAnswer ? "Save changes" : "Create"}
            >
              <FormField htmlFor="model-answer-content" label="Content" required>
                <Textarea
                  id="model-answer-content"
                  required
                  value={modelAnswerForm.content}
                  onChange={(event) =>
                    setModelAnswerForm({ ...modelAnswerForm, content: event.target.value })
                  }
                />
              </FormField>
              <FormField htmlFor="model-answer-marks" label="Marks Allocated">
                <Input
                  id="model-answer-marks"
                  type="number"
                  step="0.01"
                  value={modelAnswerForm.marks_allocated ?? ""}
                  onChange={(event) =>
                    setModelAnswerForm({
                      ...modelAnswerForm,
                      marks_allocated: event.target.value === "" ? null : Number(event.target.value),
                    })
                  }
                />
              </FormField>
              <FormField htmlFor="model-answer-order" label="Display Order" required>
                <Input
                  id="model-answer-order"
                  type="number"
                  required
                  value={modelAnswerForm.display_order ?? 0}
                  onChange={(event) =>
                    setModelAnswerForm({ ...modelAnswerForm, display_order: Number(event.target.value) })
                  }
                />
              </FormField>
            </FormDialog>
            <ConfirmDialog
              open={deletingModelAnswer !== null}
              onOpenChange={(open) => !open && setDeletingModelAnswer(null)}
              title="Delete model answer?"
              description="This model answer will be soft-deleted and can be restored later."
              confirmLabel="Delete"
              variant="destructive"
              isConfirming={removeModelAnswerMutation.isPending}
              onConfirm={() =>
                deletingModelAnswer &&
                removeModelAnswerMutation.mutate(deletingModelAnswer.id, {
                  onSuccess: () => setDeletingModelAnswer(null),
                })
              }
            />
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Alternative Answers</h2>
              {canCreateAlternativeAnswer && (
                <Button size="sm" onClick={openCreateAlternativeAnswer}>
                  <Plus className="h-4 w-4" />
                  Add Alternative Answer
                </Button>
              )}
            </div>
            <DataTable
              columns={alternativeAnswerColumns}
              rows={alternativeAnswers}
              getRowId={(row) => row.id}
              isLoading={alternativeAnswersList.isLoading}
              isError={alternativeAnswersList.isError}
              emptyMessage="No alternative answers found."
              renderActions={(row) => (
                <div className="flex justify-end gap-1">
                  {canUpdateAlternativeAnswer && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit alternative answer ${row.id}`}
                      onClick={() => openEditAlternativeAnswer(row)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  )}
                  {canDeleteAlternativeAnswer && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete alternative answer ${row.id}`}
                      onClick={() => setDeletingAlternativeAnswer(row)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            />
            <FormDialog
              open={alternativeAnswerFormOpen}
              onOpenChange={setAlternativeAnswerFormOpen}
              title={editingAlternativeAnswer ? "Edit Alternative Answer" : "New Alternative Answer"}
              onSubmit={handleAlternativeAnswerSubmit}
              isSubmitting={
                createAlternativeAnswerMutation.isPending || updateAlternativeAnswerMutation.isPending
              }
              submitLabel={editingAlternativeAnswer ? "Save changes" : "Create"}
            >
              <FormField htmlFor="alternative-answer-content" label="Content" required>
                <Textarea
                  id="alternative-answer-content"
                  required
                  value={alternativeAnswerForm.content}
                  onChange={(event) =>
                    setAlternativeAnswerForm({ ...alternativeAnswerForm, content: event.target.value })
                  }
                />
              </FormField>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={alternativeAnswerForm.is_exact_match ?? false}
                  onChange={(event) =>
                    setAlternativeAnswerForm({
                      ...alternativeAnswerForm,
                      is_exact_match: event.target.checked,
                    })
                  }
                />
                Exact match
              </label>
            </FormDialog>
            <ConfirmDialog
              open={deletingAlternativeAnswer !== null}
              onOpenChange={(open) => !open && setDeletingAlternativeAnswer(null)}
              title="Delete alternative answer?"
              description="This alternative answer will be soft-deleted and can be restored later."
              confirmLabel="Delete"
              variant="destructive"
              isConfirming={removeAlternativeAnswerMutation.isPending}
              onConfirm={() =>
                deletingAlternativeAnswer &&
                removeAlternativeAnswerMutation.mutate(deletingAlternativeAnswer.id, {
                  onSuccess: () => setDeletingAlternativeAnswer(null),
                })
              }
            />
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Reference Notes</h2>
              {canCreateReferenceNote && (
                <Button size="sm" onClick={openCreateReferenceNote}>
                  <Plus className="h-4 w-4" />
                  Add Reference Note
                </Button>
              )}
            </div>
            <DataTable
              columns={referenceNoteColumns}
              rows={referenceNotes}
              getRowId={(row) => row.id}
              isLoading={referenceNotesList.isLoading}
              isError={referenceNotesList.isError}
              emptyMessage="No reference notes found."
              renderActions={(row) => (
                <div className="flex justify-end gap-1">
                  {canUpdateReferenceNote && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit reference note ${row.id}`}
                      onClick={() => openEditReferenceNote(row)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  )}
                  {canDeleteReferenceNote && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete reference note ${row.id}`}
                      onClick={() => setDeletingReferenceNote(row)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            />
            <FormDialog
              open={referenceNoteFormOpen}
              onOpenChange={setReferenceNoteFormOpen}
              title={editingReferenceNote ? "Edit Reference Note" : "New Reference Note"}
              onSubmit={handleReferenceNoteSubmit}
              isSubmitting={createReferenceNoteMutation.isPending || updateReferenceNoteMutation.isPending}
              submitLabel={editingReferenceNote ? "Save changes" : "Create"}
            >
              <FormField htmlFor="reference-note-text" label="Note" required>
                <Textarea
                  id="reference-note-text"
                  required
                  value={referenceNoteForm.note_text}
                  onChange={(event) =>
                    setReferenceNoteForm({ ...referenceNoteForm, note_text: event.target.value })
                  }
                />
              </FormField>
              <FormField htmlFor="reference-note-type" label="Type">
                <Select
                  id="reference-note-type"
                  value={referenceNoteForm.note_type ?? "teacher_note"}
                  onChange={(event) =>
                    setReferenceNoteForm({
                      ...referenceNoteForm,
                      note_type: event.target.value as NoteType,
                    })
                  }
                >
                  {noteTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </FormField>
            </FormDialog>
            <ConfirmDialog
              open={deletingReferenceNote !== null}
              onOpenChange={(open) => !open && setDeletingReferenceNote(null)}
              title="Delete reference note?"
              description="This reference note will be soft-deleted and can be restored later."
              confirmLabel="Delete"
              variant="destructive"
              isConfirming={removeReferenceNoteMutation.isPending}
              onConfirm={() =>
                deletingReferenceNote &&
                removeReferenceNoteMutation.mutate(deletingReferenceNote.id, {
                  onSuccess: () => setDeletingReferenceNote(null),
                })
              }
            />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Expected Keywords &amp; Concepts</h2>
            <div className="flex flex-col gap-6 lg:flex-row">
              <div className="flex-1">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-medium text-muted-foreground">Expected Keywords</h3>
                  {canCreateExpectedKeyword && (
                    <Button size="sm" onClick={openCreateExpectedKeyword}>
                      <Plus className="h-4 w-4" />
                      Add Keyword
                    </Button>
                  )}
                </div>
                <DataTable
                  columns={expectedKeywordColumns}
                  rows={expectedKeywords}
                  getRowId={(row) => row.id}
                  isLoading={expectedKeywordsList.isLoading}
                  isError={expectedKeywordsList.isError}
                  emptyMessage="No expected keywords found."
                  renderActions={(row) => (
                    <div className="flex justify-end gap-1">
                      {canUpdateExpectedKeyword && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit expected keyword ${row.keyword}`}
                          onClick={() => openEditExpectedKeyword(row)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {canDeleteExpectedKeyword && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete expected keyword ${row.keyword}`}
                          onClick={() => setDeletingExpectedKeyword(row)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  )}
                />
                <FormDialog
                  open={expectedKeywordFormOpen}
                  onOpenChange={setExpectedKeywordFormOpen}
                  title={editingExpectedKeyword ? "Edit Expected Keyword" : "New Expected Keyword"}
                  onSubmit={handleExpectedKeywordSubmit}
                  isSubmitting={
                    createExpectedKeywordMutation.isPending || updateExpectedKeywordMutation.isPending
                  }
                  submitLabel={editingExpectedKeyword ? "Save changes" : "Create"}
                >
                  <FormField htmlFor="expected-keyword-keyword" label="Keyword" required>
                    <Input
                      id="expected-keyword-keyword"
                      required
                      value={expectedKeywordForm.keyword}
                      onChange={(event) =>
                        setExpectedKeywordForm({ ...expectedKeywordForm, keyword: event.target.value })
                      }
                    />
                  </FormField>
                  <FormField htmlFor="expected-keyword-weight" label="Weight">
                    <Input
                      id="expected-keyword-weight"
                      type="number"
                      step="0.01"
                      value={expectedKeywordForm.weight ?? ""}
                      onChange={(event) =>
                        setExpectedKeywordForm({
                          ...expectedKeywordForm,
                          weight: event.target.value === "" ? null : Number(event.target.value),
                        })
                      }
                    />
                  </FormField>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={expectedKeywordForm.is_mandatory ?? false}
                      onChange={(event) =>
                        setExpectedKeywordForm({
                          ...expectedKeywordForm,
                          is_mandatory: event.target.checked,
                        })
                      }
                    />
                    Mandatory
                  </label>
                </FormDialog>
                <ConfirmDialog
                  open={deletingExpectedKeyword !== null}
                  onOpenChange={(open) => !open && setDeletingExpectedKeyword(null)}
                  title="Delete expected keyword?"
                  description="This expected keyword will be soft-deleted and can be restored later."
                  confirmLabel="Delete"
                  variant="destructive"
                  isConfirming={removeExpectedKeywordMutation.isPending}
                  onConfirm={() =>
                    deletingExpectedKeyword &&
                    removeExpectedKeywordMutation.mutate(deletingExpectedKeyword.id, {
                      onSuccess: () => setDeletingExpectedKeyword(null),
                    })
                  }
                />
              </div>

              <div className="flex-1">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-medium text-muted-foreground">Expected Concepts</h3>
                  {canCreateExpectedConcept && (
                    <Button size="sm" onClick={openCreateExpectedConcept}>
                      <Plus className="h-4 w-4" />
                      Add Concept
                    </Button>
                  )}
                </div>
                <DataTable
                  columns={expectedConceptColumns}
                  rows={expectedConcepts}
                  getRowId={(row) => row.id}
                  isLoading={expectedConceptsList.isLoading}
                  isError={expectedConceptsList.isError}
                  emptyMessage="No expected concepts found."
                  renderActions={(row) => (
                    <div className="flex justify-end gap-1">
                      {canUpdateExpectedConcept && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit expected concept ${row.concept_name}`}
                          onClick={() => openEditExpectedConcept(row)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {canDeleteExpectedConcept && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete expected concept ${row.concept_name}`}
                          onClick={() => setDeletingExpectedConcept(row)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  )}
                />
                <FormDialog
                  open={expectedConceptFormOpen}
                  onOpenChange={setExpectedConceptFormOpen}
                  title={editingExpectedConcept ? "Edit Expected Concept" : "New Expected Concept"}
                  onSubmit={handleExpectedConceptSubmit}
                  isSubmitting={
                    createExpectedConceptMutation.isPending || updateExpectedConceptMutation.isPending
                  }
                  submitLabel={editingExpectedConcept ? "Save changes" : "Create"}
                >
                  <FormField htmlFor="expected-concept-name" label="Concept Name" required>
                    <Input
                      id="expected-concept-name"
                      required
                      value={expectedConceptForm.concept_name}
                      onChange={(event) =>
                        setExpectedConceptForm({
                          ...expectedConceptForm,
                          concept_name: event.target.value,
                        })
                      }
                    />
                  </FormField>
                  <FormField htmlFor="expected-concept-description" label="Description">
                    <Textarea
                      id="expected-concept-description"
                      value={expectedConceptForm.description ?? ""}
                      onChange={(event) =>
                        setExpectedConceptForm({
                          ...expectedConceptForm,
                          description: event.target.value,
                        })
                      }
                    />
                  </FormField>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={expectedConceptForm.is_mandatory ?? false}
                      onChange={(event) =>
                        setExpectedConceptForm({
                          ...expectedConceptForm,
                          is_mandatory: event.target.checked,
                        })
                      }
                    />
                    Mandatory
                  </label>
                </FormDialog>
                <ConfirmDialog
                  open={deletingExpectedConcept !== null}
                  onOpenChange={(open) => !open && setDeletingExpectedConcept(null)}
                  title="Delete expected concept?"
                  description="This expected concept will be soft-deleted and can be restored later."
                  confirmLabel="Delete"
                  variant="destructive"
                  isConfirming={removeExpectedConceptMutation.isPending}
                  onConfirm={() =>
                    deletingExpectedConcept &&
                    removeExpectedConceptMutation.mutate(deletingExpectedConcept.id, {
                      onSuccess: () => setDeletingExpectedConcept(null),
                    })
                  }
                />
              </div>
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Answer Key Builder"
        description="Manage answer keys and their model answers, alternative answers, reference notes, and expected keywords/concepts."
        actions={
          canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New Answer Key
            </Button>
          )
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search answer keys..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No answer keys found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Manage details for ${questionLabel(row.question_id)}`}
              onClick={() => openDetail(row)}
            >
              <FileText className="h-4 w-4" />
            </Button>
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit answer key for ${questionLabel(row.question_id)}`}
                onClick={() => openEdit(row)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete answer key for ${questionLabel(row.question_id)}`}
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
        title={editing ? "Edit Answer Key" : "New Answer Key"}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <FormField htmlFor="answer-key-question" label="Question" required>
          <Select
            id="answer-key-question"
            required
            value={form.question_id}
            onChange={(event) => setForm({ ...form, question_id: event.target.value })}
          >
            <option value="" disabled>
              Select a question
            </option>
            {questions?.map((question) => (
              <option key={question.id} value={question.id}>
                {truncate(question.question_text, 50)}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="answer-key-reference-answer" label="Reference Answer" required>
          <Textarea
            id="answer-key-reference-answer"
            required
            value={form.reference_answer}
            onChange={(event) => setForm({ ...form, reference_answer: event.target.value })}
          />
        </FormField>
        <FormField htmlFor="answer-key-expected-length" label="Expected Length">
          <Input
            id="answer-key-expected-length"
            type="number"
            value={form.expected_length ?? ""}
            onChange={(event) =>
              setForm({
                ...form,
                expected_length: event.target.value === "" ? null : Number(event.target.value),
              })
            }
          />
        </FormField>
        <FormField htmlFor="answer-key-evaluation-notes" label="Evaluation Notes">
          <Textarea
            id="answer-key-evaluation-notes"
            value={form.evaluation_notes ?? ""}
            onChange={(event) => setForm({ ...form, evaluation_notes: event.target.value })}
          />
        </FormField>
      </FormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete answer key?"
        description={`The answer key for "${deleting ? questionLabel(deleting.question_id) : ""}" will be soft-deleted and can be restored later.`}
        confirmLabel="Delete"
        variant="destructive"
        isConfirming={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  );
}
