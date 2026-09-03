import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { QuestionEditorPage } from "@/pages/assessment/QuestionEditorPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Question } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { getMock, createMock, updateMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
}));
vi.mock("@/api/questions", () => ({
  questionsApi: {
    list: vi.fn(),
    listDeleted: vi.fn(),
    get: getMock,
    create: createMock,
    update: updateMock,
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

function optionsPage<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
}

vi.mock("@/api/subjects", () => ({
  subjectsApi: {
    list: vi.fn().mockResolvedValue(
      optionsPage([{ id: "subject-1", name: "Subject A" }]),
    ),
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    restore: vi.fn(),
  },
}));

vi.mock("@/api/questionCategories", () => ({
  questionCategoriesApi: {
    list: vi.fn().mockResolvedValue(
      optionsPage([{ id: "category-1", name: "Category A" }]),
    ),
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
    list: vi.fn().mockResolvedValue(optionsPage([{ id: "type-1", name: "Type A" }])),
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
    list: vi.fn().mockResolvedValue(
      optionsPage([{ id: "difficulty-1", name: "Difficulty A" }]),
    ),
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
    list: vi.fn().mockResolvedValue(optionsPage([{ id: "bloom-1", name: "Bloom A" }])),
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
  permissions: ["questions:create", "questions:read", "questions:update"],
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

function renderPage(initialEntry: string) {
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
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/dashboard/questions/new" element={<QuestionEditorPage />} />
            <Route path="/dashboard/questions/:id/edit" element={<QuestionEditorPage />} />
          </Routes>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionEditorPage", () => {
  it("creates a question", async () => {
    createMock.mockResolvedValueOnce(question);
    renderPage("/dashboard/questions/new");

    expect(await screen.findByText("New Question")).toBeInTheDocument();

    await userEvent.selectOptions(await screen.findByLabelText(/^Subject/), "subject-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Category/), "category-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Type/), "type-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Difficulty Level/), "difficulty-1");
    await userEvent.selectOptions(screen.getByLabelText(/^Bloom Level/), "bloom-1");
    await userEvent.type(
      screen.getByLabelText(/^Question Text/),
      "What is the capital of France?",
    );

    const marksInput = screen.getByLabelText(/^Marks/);
    await userEvent.clear(marksInput);
    await userEvent.type(marksInput, "5");

    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          subject_id: "subject-1",
          question_category_id: "category-1",
          question_type_id: "type-1",
          difficulty_level_id: "difficulty-1",
          bloom_level_id: "bloom-1",
          question_text: "What is the capital of France?",
          marks: 5,
        }),
      ),
    );
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/dashboard/questions/question-1"));
  });

  it("pre-fills and updates an existing question", async () => {
    getMock.mockResolvedValueOnce(question);
    updateMock.mockResolvedValueOnce(question);
    renderPage("/dashboard/questions/question-1/edit");

    expect(await screen.findByText("Edit Question")).toBeInTheDocument();
    expect(getMock).toHaveBeenCalledWith("question-1");

    const questionTextInput = await screen.findByLabelText(/^Question Text/);
    await waitFor(() =>
      expect(questionTextInput).toHaveValue("What is the capital of France?"),
    );

    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        "question-1",
        expect.objectContaining({
          subject_id: "subject-1",
          question_text: "What is the capital of France?",
          marks: 5,
        }),
      ),
    );
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/dashboard/questions/question-1"));
  });
});
