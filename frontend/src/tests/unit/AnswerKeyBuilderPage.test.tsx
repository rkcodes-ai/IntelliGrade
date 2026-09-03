import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { AnswerKeyBuilderPage } from "@/pages/assessment/AnswerKeyBuilderPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type {
  AlternativeAnswer,
  AnswerKey,
  ExpectedConcept,
  ExpectedKeyword,
  ModelAnswer,
  Question,
  ReferenceNote,
} from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  answerKeysListMock,
  answerKeysCreateMock,
  answerKeysUpdateMock,
  answerKeysRemoveMock,
  questionsListMock,
  modelAnswersListMock,
  modelAnswersCreateMock,
  modelAnswersUpdateMock,
  modelAnswersRemoveMock,
  alternativeAnswersListMock,
  alternativeAnswersCreateMock,
  alternativeAnswersUpdateMock,
  alternativeAnswersRemoveMock,
  referenceNotesListMock,
  referenceNotesCreateMock,
  referenceNotesUpdateMock,
  referenceNotesRemoveMock,
  expectedKeywordsListMock,
  expectedKeywordsCreateMock,
  expectedKeywordsUpdateMock,
  expectedKeywordsRemoveMock,
  expectedConceptsListMock,
  expectedConceptsCreateMock,
  expectedConceptsUpdateMock,
  expectedConceptsRemoveMock,
} = vi.hoisted(() => ({
  answerKeysListMock: vi.fn(),
  answerKeysCreateMock: vi.fn(),
  answerKeysUpdateMock: vi.fn(),
  answerKeysRemoveMock: vi.fn(),
  questionsListMock: vi.fn(),
  modelAnswersListMock: vi.fn(),
  modelAnswersCreateMock: vi.fn(),
  modelAnswersUpdateMock: vi.fn(),
  modelAnswersRemoveMock: vi.fn(),
  alternativeAnswersListMock: vi.fn(),
  alternativeAnswersCreateMock: vi.fn(),
  alternativeAnswersUpdateMock: vi.fn(),
  alternativeAnswersRemoveMock: vi.fn(),
  referenceNotesListMock: vi.fn(),
  referenceNotesCreateMock: vi.fn(),
  referenceNotesUpdateMock: vi.fn(),
  referenceNotesRemoveMock: vi.fn(),
  expectedKeywordsListMock: vi.fn(),
  expectedKeywordsCreateMock: vi.fn(),
  expectedKeywordsUpdateMock: vi.fn(),
  expectedKeywordsRemoveMock: vi.fn(),
  expectedConceptsListMock: vi.fn(),
  expectedConceptsCreateMock: vi.fn(),
  expectedConceptsUpdateMock: vi.fn(),
  expectedConceptsRemoveMock: vi.fn(),
}));

vi.mock("@/api/answerKeys", () => ({
  answerKeysApi: {
    list: answerKeysListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: answerKeysCreateMock,
    update: answerKeysUpdateMock,
    remove: answerKeysRemoveMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/questions", () => ({
  questionsApi: {
    list: questionsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/modelAnswers", () => ({
  modelAnswersApi: {
    list: modelAnswersListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: modelAnswersCreateMock,
    update: modelAnswersUpdateMock,
    remove: modelAnswersRemoveMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/alternativeAnswers", () => ({
  alternativeAnswersApi: {
    list: alternativeAnswersListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: alternativeAnswersCreateMock,
    update: alternativeAnswersUpdateMock,
    remove: alternativeAnswersRemoveMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/referenceNotes", () => ({
  referenceNotesApi: {
    list: referenceNotesListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: referenceNotesCreateMock,
    update: referenceNotesUpdateMock,
    remove: referenceNotesRemoveMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/expectedKeywords", () => ({
  expectedKeywordsApi: {
    list: expectedKeywordsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: expectedKeywordsCreateMock,
    update: expectedKeywordsUpdateMock,
    remove: expectedKeywordsRemoveMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/expectedConcepts", () => ({
  expectedConceptsApi: {
    list: expectedConceptsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: expectedConceptsCreateMock,
    update: expectedConceptsUpdateMock,
    remove: expectedConceptsRemoveMock,
    restore: vi.fn(),
  },
}));

const baseUser: User = {
  id: "user-1",
  email: "admin@example.com",
  username: "admin",
  full_name: "Admin",
  phone: null,
  avatar_url: null,
  timezone: "UTC",
  language: "en",
  preferences: {},
  is_active: true,
  is_verified: true,
  roles: ["institution_admin"],
  permissions: [
    "answer_keys:create",
    "answer_keys:read",
    "answer_keys:update",
    "answer_keys:delete",
    "model_answers:create",
    "model_answers:read",
    "model_answers:update",
    "model_answers:delete",
    "alternative_answers:create",
    "alternative_answers:read",
    "alternative_answers:update",
    "alternative_answers:delete",
    "reference_notes:create",
    "reference_notes:read",
    "reference_notes:update",
    "reference_notes:delete",
    "expected_keywords:create",
    "expected_keywords:read",
    "expected_keywords:update",
    "expected_keywords:delete",
    "expected_concepts:create",
    "expected_concepts:read",
    "expected_concepts:update",
    "expected_concepts:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const question: Question = {
  id: "question-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  question_category_id: "category-1",
  question_type_id: "type-1",
  difficulty_level_id: "difficulty-1",
  bloom_level_id: "bloom-1",
  unit: null,
  chapter: null,
  topic: null,
  subtopic: null,
  learning_outcome: null,
  question_text: "What is the capital of France?",
  estimated_time_minutes: null,
  marks: "5.00",
  language: "en",
  attachments: null,
  diagram_url: null,
  question_metadata: null,
  is_active: true,
  current_version: 1,
  approval_status: "approved",
  approved_by: null,
  approved_at: null,
  rejection_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const answerKey: AnswerKey = {
  id: "key-1",
  institution_id: "inst-1",
  question_id: "question-1",
  reference_answer: "Paris is the capital of France.",
  expected_length: null,
  expected_structure: null,
  confidence_threshold: null,
  ai_config: null,
  evaluation_notes: null,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const modelAnswer: ModelAnswer = {
  id: "model-answer-1",
  institution_id: "inst-1",
  answer_key_id: "key-1",
  content: "Paris.",
  marks_allocated: null,
  display_order: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const alternativeAnswer: AlternativeAnswer = {
  id: "alt-answer-1",
  institution_id: "inst-1",
  answer_key_id: "key-1",
  content: "The capital of France is Paris.",
  is_exact_match: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const referenceNote: ReferenceNote = {
  id: "ref-note-1",
  institution_id: "inst-1",
  answer_key_id: "key-1",
  note_text: "Accept phonetic spellings.",
  note_type: "teacher_note",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const expectedKeyword: ExpectedKeyword = {
  id: "keyword-1",
  institution_id: "inst-1",
  answer_key_id: "key-1",
  rubric_criterion_id: null,
  keyword: "Paris",
  weight: null,
  is_mandatory: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const expectedConcept: ExpectedConcept = {
  id: "concept-1",
  institution_id: "inst-1",
  answer_key_id: "key-1",
  rubric_criterion_id: null,
  concept_name: "Capital city",
  description: null,
  is_mandatory: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page<T>(items: T[], pageSize = 20): Page<T> {
  return { items, total: items.length, page: 1, page_size: pageSize, total_pages: 1 };
}

function renderPage() {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: baseUser, accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter>
          <ToastProvider>
            <AnswerKeyBuilderPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("AnswerKeyBuilderPage", () => {
  beforeEach(() => {
    // Shared defaults for the four nested sub-panel lists plus the question
    // lookup — kept resolved-to-empty so tests that don't care about a given
    // sub-panel don't need to stub every one individually.
    questionsListMock.mockResolvedValue(page([question], 200));
    modelAnswersListMock.mockResolvedValue(page([], 200));
    alternativeAnswersListMock.mockResolvedValue(page([], 200));
    referenceNotesListMock.mockResolvedValue(page([], 200));
    expectedKeywordsListMock.mockResolvedValue(page([], 200));
    expectedConceptsListMock.mockResolvedValue(page([], 200));
  });

  it("lists answer keys for the current institution", async () => {
    answerKeysListMock.mockResolvedValueOnce(page([answerKey]));
    questionsListMock.mockResolvedValue(page([question], 200));
    modelAnswersListMock.mockResolvedValue(page([], 200));

    renderPage();

    expect(await screen.findByText("What is the capital of France?")).toBeInTheDocument();
    expect(screen.getByText("Paris is the capital of France.")).toBeInTheDocument();
  });

  it("creates an answer key", async () => {
    answerKeysListMock.mockResolvedValue(page([]));
    questionsListMock.mockResolvedValue(page([question], 200));
    modelAnswersListMock.mockResolvedValue(page([], 200));
    answerKeysCreateMock.mockResolvedValueOnce(answerKey);

    renderPage();

    await screen.findByText("No answer keys found.");
    await userEvent.click(screen.getByRole("button", { name: "New Answer Key" }));

    await screen.findByRole("option", { name: "What is the capital of France?" });
    await userEvent.selectOptions(
      screen.getByLabelText(/^Question/),
      "question-1",
    );
    await userEvent.type(
      screen.getByLabelText(/^Reference Answer/),
      "Paris is the capital of France.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(answerKeysCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          question_id: "question-1",
          reference_answer: "Paris is the capital of France.",
        }),
      ),
    );
  });

  it("opens Manage details and shows the detail heading", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    questionsListMock.mockResolvedValue(page([question], 200));
    modelAnswersListMock.mockResolvedValue(page([], 200));

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );

    expect(
      await screen.findByText('Details for Answer Key on "What is the capital of France?"'),
    ).toBeInTheDocument();
  });

  it("creates a model answer scoped to the selected answer key", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    questionsListMock.mockResolvedValue(page([question], 200));
    modelAnswersListMock.mockResolvedValue(page([]));
    modelAnswersCreateMock.mockResolvedValueOnce(modelAnswer);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Add Model Answer" }));
    await userEvent.type(screen.getByLabelText(/^Content/), "Paris.");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(modelAnswersCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({ answer_key_id: "key-1", content: "Paris." }),
      ),
    );
  });

  it("edits an existing answer key", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    answerKeysUpdateMock.mockResolvedValueOnce({ ...answerKey, reference_answer: "Updated answer." });

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Edit answer key for What is the capital of France?" }),
    );
    const referenceAnswerInput = screen.getByLabelText(/^Reference Answer/);
    await userEvent.clear(referenceAnswerInput);
    await userEvent.type(referenceAnswerInput, "Updated answer.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(answerKeysUpdateMock).toHaveBeenCalledWith(
        "key-1",
        expect.objectContaining({ reference_answer: "Updated answer." }),
      ),
    );
  });

  it("deletes an answer key after confirmation", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    answerKeysRemoveMock.mockResolvedValueOnce(undefined);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Delete answer key for What is the capital of France?" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(answerKeysRemoveMock).toHaveBeenCalledWith("key-1"));
  });

  it("returns to the answer key list from the detail view", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Back to answer keys" }));

    expect(await screen.findByText("Answer Key Builder")).toBeInTheDocument();
  });

  it("edits and deletes a model answer", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    modelAnswersListMock.mockResolvedValue(page([modelAnswer]));
    modelAnswersUpdateMock.mockResolvedValueOnce({ ...modelAnswer, content: "Paris, France." });
    modelAnswersRemoveMock.mockResolvedValueOnce(undefined);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Edit model answer 0" }));
    const contentInput = screen.getByLabelText(/^Content/);
    await userEvent.clear(contentInput);
    await userEvent.type(contentInput, "Paris, France.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(modelAnswersUpdateMock).toHaveBeenCalledWith(
        "model-answer-1",
        expect.objectContaining({ content: "Paris, France." }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete model answer 0" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(modelAnswersRemoveMock).toHaveBeenCalledWith("model-answer-1"));
  });

  it("creates an alternative answer with the exact match checkbox checked", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    alternativeAnswersCreateMock.mockResolvedValueOnce(alternativeAnswer);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Add Alternative Answer" }));
    await userEvent.type(screen.getByLabelText(/^Content/), "The capital of France is Paris.");
    await userEvent.click(screen.getByLabelText("Exact match"));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(alternativeAnswersCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          answer_key_id: "key-1",
          content: "The capital of France is Paris.",
          is_exact_match: true,
        }),
      ),
    );
  });

  it("edits and deletes an alternative answer", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    alternativeAnswersListMock.mockResolvedValue(page([alternativeAnswer]));
    alternativeAnswersUpdateMock.mockResolvedValueOnce({ ...alternativeAnswer, content: "Updated." });
    alternativeAnswersRemoveMock.mockResolvedValueOnce(undefined);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Edit alternative answer alt-answer-1" }));
    const contentInput = screen.getByLabelText(/^Content/);
    await userEvent.clear(contentInput);
    await userEvent.type(contentInput, "Updated.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(alternativeAnswersUpdateMock).toHaveBeenCalledWith(
        "alt-answer-1",
        expect.objectContaining({ content: "Updated." }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete alternative answer alt-answer-1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(alternativeAnswersRemoveMock).toHaveBeenCalledWith("alt-answer-1"));
  });

  it("creates a reference note with a selected note type", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    referenceNotesCreateMock.mockResolvedValueOnce(referenceNote);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Add Reference Note" }));
    await userEvent.type(screen.getByLabelText(/^Note/), "Accept phonetic spellings.");
    await userEvent.selectOptions(screen.getByLabelText(/^Type/), "ai_note");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(referenceNotesCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          answer_key_id: "key-1",
          note_text: "Accept phonetic spellings.",
          note_type: "ai_note",
        }),
      ),
    );
  });

  it("edits and deletes a reference note", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    referenceNotesListMock.mockResolvedValue(page([referenceNote]));
    referenceNotesUpdateMock.mockResolvedValueOnce({ ...referenceNote, note_text: "Updated note." });
    referenceNotesRemoveMock.mockResolvedValueOnce(undefined);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Edit reference note ref-note-1" }));
    const noteInput = screen.getByLabelText(/^Note/);
    await userEvent.clear(noteInput);
    await userEvent.type(noteInput, "Updated note.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(referenceNotesUpdateMock).toHaveBeenCalledWith(
        "ref-note-1",
        expect.objectContaining({ note_text: "Updated note." }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete reference note ref-note-1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(referenceNotesRemoveMock).toHaveBeenCalledWith("ref-note-1"));
  });

  it("creates an expected keyword marked mandatory", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    expectedKeywordsCreateMock.mockResolvedValueOnce(expectedKeyword);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Add Keyword" }));
    await userEvent.type(screen.getByLabelText(/^Keyword/), "Paris");
    await userEvent.click(screen.getByLabelText("Mandatory"));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(expectedKeywordsCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          answer_key_id: "key-1",
          keyword: "Paris",
          is_mandatory: true,
        }),
      ),
    );
  });

  it("edits and deletes an expected keyword", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    expectedKeywordsListMock.mockResolvedValue(page([expectedKeyword]));
    expectedKeywordsUpdateMock.mockResolvedValueOnce({ ...expectedKeyword, keyword: "Paris, France" });
    expectedKeywordsRemoveMock.mockResolvedValueOnce(undefined);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Edit expected keyword Paris" }));
    const keywordInput = screen.getByLabelText(/^Keyword/);
    await userEvent.clear(keywordInput);
    await userEvent.type(keywordInput, "Paris, France");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(expectedKeywordsUpdateMock).toHaveBeenCalledWith(
        "keyword-1",
        expect.objectContaining({ keyword: "Paris, France" }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete expected keyword Paris" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(expectedKeywordsRemoveMock).toHaveBeenCalledWith("keyword-1"));
  });

  it("creates an expected concept with a description and marked mandatory", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    expectedConceptsCreateMock.mockResolvedValueOnce(expectedConcept);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Add Concept" }));
    await userEvent.type(screen.getByLabelText(/^Concept Name/), "Capital city");
    await userEvent.type(screen.getByLabelText(/^Description/), "The seat of national government.");
    await userEvent.click(screen.getByLabelText("Mandatory"));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(expectedConceptsCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          answer_key_id: "key-1",
          concept_name: "Capital city",
          description: "The seat of national government.",
          is_mandatory: true,
        }),
      ),
    );
  });

  it("edits and deletes an expected concept", async () => {
    answerKeysListMock.mockResolvedValue(page([answerKey]));
    expectedConceptsListMock.mockResolvedValue(page([expectedConcept]));
    expectedConceptsUpdateMock.mockResolvedValueOnce({
      ...expectedConcept,
      concept_name: "Capital city of France",
    });
    expectedConceptsRemoveMock.mockResolvedValueOnce(undefined);

    renderPage();

    await screen.findByText("Paris is the capital of France.");
    await userEvent.click(
      screen.getByRole("button", { name: "Manage details for What is the capital of France?" }),
    );
    await screen.findByText('Details for Answer Key on "What is the capital of France?"');

    await userEvent.click(screen.getByRole("button", { name: "Edit expected concept Capital city" }));
    const nameInput = screen.getByLabelText(/^Concept Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Capital city of France");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(expectedConceptsUpdateMock).toHaveBeenCalledWith(
        "concept-1",
        expect.objectContaining({ concept_name: "Capital city of France" }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete expected concept Capital city" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(expectedConceptsRemoveMock).toHaveBeenCalledWith("concept-1"));
  });
});
