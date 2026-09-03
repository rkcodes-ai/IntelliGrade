import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { QuestionReviewScreenPage } from "@/pages/assessment/QuestionReviewScreenPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { QuestionReview } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { listMock, createMock, updateMock, removeMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
}));
vi.mock("@/api/questionReviews", () => ({
  questionReviewsApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
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
  permissions: ["question_reviews:create", "question_reviews:update", "question_reviews:delete"],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const review: QuestionReview = {
  id: "review-1",
  institution_id: "inst-1",
  question_id: "q-1",
  reviewer_id: "user-1",
  comment: "Well-written question, clear phrasing.",
  rating: 4,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

const otherQuestionReview: QuestionReview = {
  id: "review-2",
  institution_id: "inst-1",
  question_id: "q-2",
  reviewer_id: "user-1",
  comment: "This belongs to a different question.",
  rating: 2,
  created_at: "2026-01-03T00:00:00Z",
  updated_at: "2026-01-03T00:00:00Z",
};

function page(items: QuestionReview[]): Page<QuestionReview> {
  return { items, total: items.length, page: 1, page_size: 200, total_pages: 1 };
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
        <MemoryRouter initialEntries={["/dashboard/questions/q-1/reviews"]}>
          <ToastProvider>
            <Routes>
              <Route path="/dashboard/questions/:id/reviews" element={<QuestionReviewScreenPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("QuestionReviewScreenPage", () => {
  it("lists reviews filtered to the current question", async () => {
    listMock.mockResolvedValueOnce(page([review, otherQuestionReview]));
    renderPage();

    expect(await screen.findByText("Well-written question, clear phrasing.")).toBeInTheDocument();
    expect(screen.queryByText("This belongs to a different question.")).not.toBeInTheDocument();
  });

  it("creates a review", async () => {
    listMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(review);
    renderPage();

    await screen.findByText("No reviews found.");
    await userEvent.click(screen.getByRole("button", { name: "New Review" }));
    await userEvent.type(screen.getByLabelText(/^Comment/), "Well-written question, clear phrasing.");
    await userEvent.type(screen.getByLabelText(/^Rating/), "4");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith({
        question_id: "q-1",
        comment: "Well-written question, clear phrasing.",
        rating: 4,
      }),
    );
  });

  it("deletes a review after confirmation", async () => {
    listMock.mockResolvedValue(page([review]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Well-written question, clear phrasing.");
    await userEvent.click(screen.getByRole("button", { name: "Delete review review-1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("review-1"));
  });
});
