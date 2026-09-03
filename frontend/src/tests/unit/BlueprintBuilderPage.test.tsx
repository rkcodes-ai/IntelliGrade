import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { BlueprintBuilderPage } from "@/pages/assessment/BlueprintBuilderPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { QuestionBlueprint, QuestionBlueprintSection } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  listMock,
  createMock,
  updateMock,
  removeMock,
  subjectsListMock,
  sectionsListMock,
  sectionsCreateMock,
  sectionsUpdateMock,
  sectionsRemoveMock,
  categoriesListMock,
  difficultyLevelsListMock,
  bloomLevelsListMock,
  questionTypesListMock,
} = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  subjectsListMock: vi.fn(),
  sectionsListMock: vi.fn(),
  sectionsCreateMock: vi.fn(),
  sectionsUpdateMock: vi.fn(),
  sectionsRemoveMock: vi.fn(),
  categoriesListMock: vi.fn(),
  difficultyLevelsListMock: vi.fn(),
  bloomLevelsListMock: vi.fn(),
  questionTypesListMock: vi.fn(),
}));

vi.mock("@/api/questionBlueprints", () => ({
  questionBlueprintsApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/subjects", () => ({
  subjectsApi: {
    list: subjectsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/questionBlueprintSections", () => ({
  questionBlueprintSectionsApi: {
    list: sectionsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: sectionsCreateMock,
    update: sectionsUpdateMock,
    remove: sectionsRemoveMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/questionCategories", () => ({
  questionCategoriesApi: {
    list: categoriesListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/difficultyLevels", () => ({
  difficultyLevelsApi: {
    list: difficultyLevelsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/bloomTaxonomyLevels", () => ({
  bloomTaxonomyLevelsApi: {
    list: bloomLevelsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));
vi.mock("@/api/questionTypes", () => ({
  questionTypesApi: {
    list: questionTypesListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
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
    "question_blueprints:create",
    "question_blueprints:read",
    "question_blueprints:update",
    "question_blueprints:delete",
    "question_blueprint_sections:create",
    "question_blueprint_sections:read",
    "question_blueprint_sections:update",
    "question_blueprint_sections:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const blueprint: QuestionBlueprint = {
  id: "blueprint-1",
  institution_id: "inst-1",
  subject_id: "subject-1",
  name: "Midterm Blueprint",
  total_marks: "100.00",
  total_questions: 50,
  is_active: true,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const section: QuestionBlueprintSection = {
  id: "section-1",
  institution_id: "inst-1",
  blueprint_id: "blueprint-1",
  question_category_id: "category-1",
  difficulty_level_id: "difficulty-1",
  bloom_level_id: "bloom-1",
  question_type_id: "type-1",
  number_of_questions: 10,
  marks_per_question: "2.00",
  display_order: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
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
            <BlueprintBuilderPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("BlueprintBuilderPage", () => {
  beforeEach(() => {
    // Shared select-option lookups needed by both the master form and the
    // nested sections form — kept resolved-to-empty by default so tests that
    // don't care about them don't need to stub every one individually.
    subjectsListMock.mockResolvedValue(page([{ id: "subject-1", name: "Mathematics" }]));
    categoriesListMock.mockResolvedValue(page([]));
    difficultyLevelsListMock.mockResolvedValue(page([]));
    bloomLevelsListMock.mockResolvedValue(page([]));
    questionTypesListMock.mockResolvedValue(page([]));
    sectionsListMock.mockResolvedValue(page([]));
  });

  it("lists blueprints", async () => {
    listMock.mockResolvedValueOnce(page([blueprint]));
    renderPage();
    expect(await screen.findByText("Midterm Blueprint")).toBeInTheDocument();
    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
  });

  it("creates a blueprint", async () => {
    listMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(blueprint);
    renderPage();

    await screen.findByText("No blueprints found.");
    await userEvent.click(screen.getByRole("button", { name: "New Blueprint" }));
    await userEvent.selectOptions(screen.getByLabelText(/^Subject/), "subject-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Midterm Blueprint");
    await userEvent.type(screen.getByLabelText(/^Total Marks/), "100");
    await userEvent.type(screen.getByLabelText(/^Total Questions/), "50");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          subject_id: "subject-1",
          name: "Midterm Blueprint",
          total_marks: 100,
          total_questions: 50,
        }),
      ),
    );
  });

  it("opens the sections panel for a blueprint", async () => {
    listMock.mockResolvedValue(page([blueprint]));
    renderPage();

    await screen.findByText("Midterm Blueprint");
    await userEvent.click(screen.getByRole("button", { name: `Manage sections for ${blueprint.name}` }));

    expect(await screen.findByText(`Sections for "${blueprint.name}"`)).toBeInTheDocument();
    expect(screen.getByText("No sections found.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to blueprints" })).toBeInTheDocument();
  });

  it("edits an existing blueprint", async () => {
    listMock.mockResolvedValue(page([blueprint]));
    updateMock.mockResolvedValueOnce({ ...blueprint, name: "Final Blueprint" });
    renderPage();

    await screen.findByText("Midterm Blueprint");
    await userEvent.click(screen.getByRole("button", { name: `Edit ${blueprint.name}` }));
    const nameInput = screen.getByLabelText(/^Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Final Blueprint");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        "blueprint-1",
        expect.objectContaining({ name: "Final Blueprint" }),
      ),
    );
  });

  it("deletes a blueprint after confirmation", async () => {
    listMock.mockResolvedValue(page([blueprint]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Blueprint");
    await userEvent.click(screen.getByRole("button", { name: `Delete ${blueprint.name}` }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("blueprint-1"));
  });

  it("creates a section leaving every optional field as Any", async () => {
    listMock.mockResolvedValue(page([blueprint]));
    sectionsCreateMock.mockResolvedValueOnce(section);
    renderPage();

    await screen.findByText("Midterm Blueprint");
    await userEvent.click(screen.getByRole("button", { name: `Manage sections for ${blueprint.name}` }));
    await screen.findByText(`Sections for "${blueprint.name}"`);

    await userEvent.click(screen.getByRole("button", { name: "New Section" }));
    await userEvent.type(screen.getByLabelText(/^# Questions/), "10");
    await userEvent.type(screen.getByLabelText(/^Marks\/Question/), "2");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(sectionsCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          blueprint_id: "blueprint-1",
          question_category_id: null,
          difficulty_level_id: null,
          bloom_level_id: null,
          question_type_id: null,
          number_of_questions: 10,
          marks_per_question: 2,
        }),
      ),
    );
  });

  it("creates a section with real category/difficulty/bloom/type selections", async () => {
    listMock.mockResolvedValue(page([blueprint]));
    categoriesListMock.mockResolvedValue(page([{ id: "category-1", name: "Algebra" }]));
    difficultyLevelsListMock.mockResolvedValue(page([{ id: "difficulty-1", name: "Medium" }]));
    bloomLevelsListMock.mockResolvedValue(page([{ id: "bloom-1", name: "Apply" }]));
    questionTypesListMock.mockResolvedValue(page([{ id: "type-1", name: "MCQ" }]));
    sectionsCreateMock.mockResolvedValueOnce(section);
    renderPage();

    await screen.findByText("Midterm Blueprint");
    await userEvent.click(screen.getByRole("button", { name: `Manage sections for ${blueprint.name}` }));
    await screen.findByText(`Sections for "${blueprint.name}"`);

    await userEvent.click(screen.getByRole("button", { name: "New Section" }));
    await screen.findByRole("option", { name: "Algebra" });
    await userEvent.selectOptions(screen.getByLabelText(/^Category/), "category-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Difficulty/), "difficulty-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Bloom Level/), "bloom-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Question Type/), "type-1");
    await userEvent.type(screen.getByLabelText(/^# Questions/), "5");
    await userEvent.type(screen.getByLabelText(/^Marks\/Question/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(sectionsCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          blueprint_id: "blueprint-1",
          question_category_id: "category-1",
          difficulty_level_id: "difficulty-1",
          bloom_level_id: "bloom-1",
          question_type_id: "type-1",
          number_of_questions: 5,
          marks_per_question: 3,
        }),
      ),
    );
  });

  it("edits a section back to Any and then deletes it", async () => {
    listMock.mockResolvedValue(page([blueprint]));
    sectionsListMock.mockResolvedValue(page([section]));
    categoriesListMock.mockResolvedValue(page([{ id: "category-1", name: "Algebra" }]));
    difficultyLevelsListMock.mockResolvedValue(page([{ id: "difficulty-1", name: "Medium" }]));
    bloomLevelsListMock.mockResolvedValue(page([{ id: "bloom-1", name: "Apply" }]));
    questionTypesListMock.mockResolvedValue(page([{ id: "type-1", name: "MCQ" }]));
    sectionsUpdateMock.mockResolvedValueOnce({ ...section, question_category_id: null });
    sectionsRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Blueprint");
    await userEvent.click(screen.getByRole("button", { name: `Manage sections for ${blueprint.name}` }));
    await screen.findByText(`Sections for "${blueprint.name}"`);
    await screen.findByText("Algebra");

    await userEvent.click(screen.getByRole("button", { name: "Edit section 0" }));
    await screen.findByRole("option", { name: "Algebra" });
    await userEvent.selectOptions(screen.getByLabelText(/^Category/), "");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(sectionsUpdateMock).toHaveBeenCalledWith(
        "section-1",
        expect.objectContaining({ question_category_id: null }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete section 0" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(sectionsRemoveMock).toHaveBeenCalledWith("section-1"));
  });
});
