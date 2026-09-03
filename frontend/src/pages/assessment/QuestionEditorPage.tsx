import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { bloomTaxonomyLevelsApi } from "@/api/bloomTaxonomyLevels";
import { difficultyLevelsApi } from "@/api/difficultyLevels";
import { questionCategoriesApi } from "@/api/questionCategories";
import { questionTypesApi } from "@/api/questionTypes";
import { questionsApi } from "@/api/questions";
import { subjectsApi } from "@/api/subjects";
import { DetailLoading } from "@/components/common/DetailState";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { useAppSelector } from "@/store";
import type { QuestionCreate } from "@/types/assessment";

const emptyForm: QuestionCreate = {
  subject_id: "",
  question_category_id: "",
  question_type_id: "",
  difficulty_level_id: "",
  bloom_level_id: "",
  unit: "",
  chapter: "",
  topic: "",
  subtopic: "",
  learning_outcome: "",
  question_text: "",
  estimated_time_minutes: undefined,
  marks: 0,
  language: "en",
  diagram_url: "",
};

/**
 * Full-page (not dialog) create/edit form for the `Question` entity — unlike
 * every other Module 04 CRUD screen, this one is reached via dedicated
 * routes (`/dashboard/questions/new` and `/dashboard/questions/:id/edit`,
 * see `QuestionBankDashboardPage`'s navigation targets) because Question has
 * too many fields to fit a `FormDialog` reasonably. On success it lands on
 * the sibling Question Viewer page at `/dashboard/questions/:id`.
 */
export function QuestionEditorPage() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === undefined;
  const navigate = useNavigate();

  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canSubmit = isNew
    ? permissions.includes("questions:create")
    : permissions.includes("questions:update");

  const { data: question, isLoading } = useQuery({
    queryKey: ["questions", id],
    queryFn: () => questionsApi.get(id!),
    enabled: !isNew,
  });

  const { data: subjects } = useSelectOptions("subjects", () => subjectsApi.list({ page_size: 200 }));
  const { data: categories } = useSelectOptions("question-categories", () =>
    questionCategoriesApi.list({ page_size: 200 }),
  );
  const { data: types } = useSelectOptions("question-types", () =>
    questionTypesApi.list({ page_size: 200 }),
  );
  const { data: difficulties } = useSelectOptions("difficulty-levels", () =>
    difficultyLevelsApi.list({ page_size: 200 }),
  );
  const { data: bloomLevels } = useSelectOptions("bloom-taxonomy-levels", () =>
    bloomTaxonomyLevelsApi.list({ page_size: 200 }),
  );

  const [form, setForm] = useState<QuestionCreate>(emptyForm);

  useEffect(() => {
    if (question) {
      setForm({
        subject_id: question.subject_id,
        question_category_id: question.question_category_id,
        question_type_id: question.question_type_id,
        difficulty_level_id: question.difficulty_level_id,
        bloom_level_id: question.bloom_level_id,
        unit: question.unit ?? "",
        chapter: question.chapter ?? "",
        topic: question.topic ?? "",
        subtopic: question.subtopic ?? "",
        learning_outcome: question.learning_outcome ?? "",
        question_text: question.question_text,
        estimated_time_minutes: question.estimated_time_minutes ?? undefined,
        marks: Number(question.marks),
        language: question.language,
        diagram_url: question.diagram_url ?? "",
      });
    }
  }, [question]);

  const createMutation = useMutation({
    mutationFn: (data: QuestionCreate) => questionsApi.create(data),
    onSuccess: (result) => navigate(`/dashboard/questions/${result.id}`),
  });
  const updateMutation = useMutation({
    mutationFn: (data: QuestionCreate) => questionsApi.update(id!, data),
    onSuccess: (result) => navigate(`/dashboard/questions/${result.id}`),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isNew) {
      createMutation.mutate(form);
    } else {
      updateMutation.mutate(form);
    }
  }

  if (!isNew && isLoading) {
    return <DetailLoading />;
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={isNew ? "New Question" : "Edit Question"}
        description={isNew ? "Add a new question to the question bank." : "Update this question's details."}
      />
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <FormField htmlFor="question-subject" label="Subject" required>
              <Select
                id="question-subject"
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

            <FormField htmlFor="question-category" label="Category" required>
              <Select
                id="question-category"
                required
                value={form.question_category_id}
                onChange={(event) => setForm({ ...form, question_category_id: event.target.value })}
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

            <FormField htmlFor="question-type" label="Type" required>
              <Select
                id="question-type"
                required
                value={form.question_type_id}
                onChange={(event) => setForm({ ...form, question_type_id: event.target.value })}
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

            <FormField htmlFor="question-difficulty" label="Difficulty Level" required>
              <Select
                id="question-difficulty"
                required
                value={form.difficulty_level_id}
                onChange={(event) => setForm({ ...form, difficulty_level_id: event.target.value })}
              >
                <option value="" disabled>
                  Select a difficulty level
                </option>
                {difficulties?.map((difficulty) => (
                  <option key={difficulty.id} value={difficulty.id}>
                    {difficulty.name}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField htmlFor="question-bloom-level" label="Bloom Level" required>
              <Select
                id="question-bloom-level"
                required
                value={form.bloom_level_id}
                onChange={(event) => setForm({ ...form, bloom_level_id: event.target.value })}
              >
                <option value="" disabled>
                  Select a Bloom level
                </option>
                {bloomLevels?.map((bloomLevel) => (
                  <option key={bloomLevel.id} value={bloomLevel.id}>
                    {bloomLevel.name}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField htmlFor="question-text" label="Question Text" required>
              <Textarea
                id="question-text"
                required
                value={form.question_text}
                onChange={(event) => setForm({ ...form, question_text: event.target.value })}
              />
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField htmlFor="question-unit" label="Unit">
                <Input
                  id="question-unit"
                  value={form.unit ?? ""}
                  onChange={(event) => setForm({ ...form, unit: event.target.value })}
                />
              </FormField>
              <FormField htmlFor="question-chapter" label="Chapter">
                <Input
                  id="question-chapter"
                  value={form.chapter ?? ""}
                  onChange={(event) => setForm({ ...form, chapter: event.target.value })}
                />
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField htmlFor="question-topic" label="Topic">
                <Input
                  id="question-topic"
                  value={form.topic ?? ""}
                  onChange={(event) => setForm({ ...form, topic: event.target.value })}
                />
              </FormField>
              <FormField htmlFor="question-subtopic" label="Subtopic">
                <Input
                  id="question-subtopic"
                  value={form.subtopic ?? ""}
                  onChange={(event) => setForm({ ...form, subtopic: event.target.value })}
                />
              </FormField>
            </div>

            <FormField htmlFor="question-learning-outcome" label="Learning Outcome">
              <Input
                id="question-learning-outcome"
                value={form.learning_outcome ?? ""}
                onChange={(event) => setForm({ ...form, learning_outcome: event.target.value })}
              />
            </FormField>

            <FormField htmlFor="question-diagram-url" label="Diagram URL">
              <Input
                id="question-diagram-url"
                value={form.diagram_url ?? ""}
                onChange={(event) => setForm({ ...form, diagram_url: event.target.value })}
              />
            </FormField>

            <div className="grid grid-cols-3 gap-4">
              <FormField htmlFor="question-marks" label="Marks" required>
                <Input
                  id="question-marks"
                  type="number"
                  step="0.01"
                  required
                  value={form.marks}
                  onChange={(event) => setForm({ ...form, marks: Number(event.target.value) })}
                />
              </FormField>
              <FormField htmlFor="question-estimated-time" label="Estimated Time (minutes)">
                <Input
                  id="question-estimated-time"
                  type="number"
                  value={form.estimated_time_minutes ?? ""}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      estimated_time_minutes:
                        event.target.value === "" ? undefined : Number(event.target.value),
                    })
                  }
                />
              </FormField>
              <FormField htmlFor="question-language" label="Language">
                <Input
                  id="question-language"
                  value={form.language ?? "en"}
                  onChange={(event) => setForm({ ...form, language: event.target.value })}
                />
              </FormField>
            </div>

            <div className="flex gap-2">
              <Button type="submit" disabled={!canSubmit || isSubmitting}>
                {isSubmitting && <Spinner className="h-4 w-4" />}
                {isNew ? "Create" : "Save changes"}
              </Button>
              <Button type="button" variant="outline" onClick={() => navigate(-1)}>
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
