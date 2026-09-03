import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { QuestionBankDashboardPage } from "@/pages/assessment/QuestionBankDashboardPage";
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

const { listMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
}));
vi.mock("@/api/questions", () => ({
  questionsApi: {
    list: listMock,
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
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 }),
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
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 }),
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
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 }),
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
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200, total_pages: 0 }),
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

function page(items: Question[]): Page<Question> {
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
            <QuestionBankDashboardPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionBankDashboardPage", () => {
  it("lists questions for the current institution", async () => {
    listMock.mockResolvedValueOnce(page([question]));
    renderPage();
    expect(await screen.findByText("What is the capital of France?")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
  });

  it("navigates to the question detail view when View is clicked", async () => {
    listMock.mockResolvedValueOnce(page([question]));
    renderPage();

    await screen.findByText("What is the capital of France?");
    await userEvent.click(screen.getByRole("button", { name: /^View/ }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/questions/question-1");
  });

  it("navigates to the new question screen when New Question is clicked", async () => {
    listMock.mockResolvedValue(page([]));
    renderPage();

    await screen.findByText("No questions found.");
    await userEvent.click(screen.getByRole("button", { name: "New Question" }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/questions/new");
  });
});
