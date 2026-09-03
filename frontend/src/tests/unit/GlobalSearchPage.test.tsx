import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { GlobalSearchPage } from "@/pages/ocr/GlobalSearchPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { SearchResults } from "@/types/teacherReview";
import type { User } from "@/types/auth";

const { globalSearchMock } = vi.hoisted(() => ({ globalSearchMock: vi.fn() }));
vi.mock("@/api/search", () => ({
  globalSearch: globalSearchMock,
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
  permissions: [],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function makeResults(overrides: Partial<SearchResults> = {}): SearchResults {
  return {
    query: "acme",
    results: [],
    ...overrides,
  };
}

function AnswerEvaluationDetailStub() {
  const { id } = useParams<{ id: string }>();
  return <div>Answer Evaluation Detail Page for {id}</div>;
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
        <MemoryRouter initialEntries={["/dashboard/search"]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/search" element={<GlobalSearchPage />} />
              <Route
                path="/dashboard/answer-evaluations/:id"
                element={<AnswerEvaluationDetailStub />}
              />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("GlobalSearchPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a placeholder message before any query is entered", () => {
    renderPage();
    expect(
      screen.getByText("Search for students, teachers, subjects, questions, or evaluations."),
    ).toBeInTheDocument();
    expect(globalSearchMock).not.toHaveBeenCalled();
  });

  it("triggers a search with the debounced query and renders results grouped by type", async () => {
    globalSearchMock.mockResolvedValueOnce(
      makeResults({
        results: [
          { type: "student", id: "s1", label: "Alice Smith", subtitle: "Grade 10" },
          { type: "student", id: "s2", label: "Bob Jones", subtitle: null },
          { type: "teacher", id: "t1", label: "Ms. Carter", subtitle: "Mathematics" },
          { type: "evaluation", id: "eval-1", label: "Evaluation eval-1", subtitle: "Session 1" },
        ],
      }),
    );
    renderPage();

    const input = screen.getByPlaceholderText(
      "Search for students, teachers, subjects, questions, or evaluations...",
    );
    fireEvent.change(input, { target: { value: "acme" } });

    await waitFor(() => expect(globalSearchMock).toHaveBeenCalledWith("acme"), { timeout: 2000 });

    expect(await screen.findByText("Students")).toBeInTheDocument();
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("Grade 10")).toBeInTheDocument();
    expect(screen.getByText("Bob Jones")).toBeInTheDocument();
    expect(screen.getByText("Teachers")).toBeInTheDocument();
    expect(screen.getByText("Ms. Carter")).toBeInTheDocument();
    expect(screen.getByText("Evaluations")).toBeInTheDocument();
    expect(screen.getByText("Evaluation eval-1")).toBeInTheDocument();

    // Sections with zero results are not rendered.
    expect(screen.queryByText("Subjects")).not.toBeInTheDocument();
    expect(screen.queryByText("Questions")).not.toBeInTheDocument();
  });

  it("navigates to the evaluation detail page when clicking an evaluation result", async () => {
    globalSearchMock.mockResolvedValueOnce(
      makeResults({
        results: [{ type: "evaluation", id: "eval-42", label: "Evaluation eval-42", subtitle: null }],
      }),
    );
    renderPage();

    fireEvent.change(
      screen.getByPlaceholderText("Search for students, teachers, subjects, questions, or evaluations..."),
      { target: { value: "eval" } },
    );

    const resultButton = await screen.findByRole("button", { name: /Evaluation eval-42/ });
    fireEvent.click(resultButton);

    expect(await screen.findByText("Answer Evaluation Detail Page for eval-42")).toBeInTheDocument();
  });

  it("shows a zero-results message when the search returns no results", async () => {
    globalSearchMock.mockResolvedValueOnce(makeResults({ results: [] }));
    renderPage();

    fireEvent.change(
      screen.getByPlaceholderText("Search for students, teachers, subjects, questions, or evaluations..."),
      { target: { value: "nomatch" } },
    );

    expect(await screen.findByText('No results found for "nomatch".')).toBeInTheDocument();
  });
});
