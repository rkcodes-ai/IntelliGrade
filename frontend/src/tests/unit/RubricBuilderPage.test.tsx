import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { RubricBuilderPage } from "@/pages/assessment/RubricBuilderPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { MarkDistribution, Rubric, RubricCriterion } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const {
  rubricsListMock,
  rubricsCreateMock,
  rubricsUpdateMock,
  rubricsRemoveMock,
  criteriaListMock,
  criteriaCreateMock,
  criteriaUpdateMock,
  criteriaRemoveMock,
  distributionsListMock,
  distributionsCreateMock,
  distributionsUpdateMock,
  distributionsRemoveMock,
} = vi.hoisted(() => ({
  rubricsListMock: vi.fn(),
  rubricsCreateMock: vi.fn(),
  rubricsUpdateMock: vi.fn(),
  rubricsRemoveMock: vi.fn(),
  criteriaListMock: vi.fn(),
  criteriaCreateMock: vi.fn(),
  criteriaUpdateMock: vi.fn(),
  criteriaRemoveMock: vi.fn(),
  distributionsListMock: vi.fn(),
  distributionsCreateMock: vi.fn(),
  distributionsUpdateMock: vi.fn(),
  distributionsRemoveMock: vi.fn(),
}));

vi.mock("@/api/rubrics", () => ({
  rubricsApi: {
    list: rubricsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: rubricsCreateMock,
    update: rubricsUpdateMock,
    remove: rubricsRemoveMock,
    restore: vi.fn(),
  },
}));

vi.mock("@/api/rubricCriteria", () => ({
  rubricCriteriaApi: {
    list: criteriaListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: criteriaCreateMock,
    update: criteriaUpdateMock,
    remove: criteriaRemoveMock,
    restore: vi.fn(),
  },
}));

vi.mock("@/api/markDistributions", () => ({
  markDistributionsApi: {
    list: distributionsListMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: distributionsCreateMock,
    update: distributionsUpdateMock,
    remove: distributionsRemoveMock,
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
    "rubrics:create",
    "rubrics:read",
    "rubrics:update",
    "rubrics:delete",
    "rubric_criteria:create",
    "rubric_criteria:read",
    "rubric_criteria:update",
    "rubric_criteria:delete",
    "mark_distributions:create",
    "mark_distributions:read",
    "mark_distributions:update",
    "mark_distributions:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const rubric: Rubric = {
  id: "rubric-1",
  institution_id: "inst-1",
  question_id: null,
  name: "Essay Rubric",
  total_marks: "20.00",
  is_active: true,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const criterion: RubricCriterion = {
  id: "criterion-1",
  institution_id: "inst-1",
  rubric_id: "rubric-1",
  parent_criterion_id: null,
  name: "Clarity",
  weightage_percent: "50.00",
  max_marks: "10.00",
  is_mandatory: true,
  teacher_notes: null,
  ai_notes: null,
  display_order: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const criterion2: RubricCriterion = {
  id: "criterion-2",
  institution_id: "inst-1",
  rubric_id: "rubric-1",
  parent_criterion_id: null,
  name: "Depth",
  weightage_percent: "50.00",
  max_marks: "10.00",
  is_mandatory: false,
  teacher_notes: null,
  ai_notes: null,
  display_order: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const markDistribution: MarkDistribution = {
  id: "dist-1",
  institution_id: "inst-1",
  rubric_criterion_id: "criterion-1",
  band_name: "Excellent",
  min_score: "8.00",
  max_score: "10.00",
  description: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function page<T>(items: T[]): Page<T> {
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
        <MemoryRouter>
          <ToastProvider>
            <RubricBuilderPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("RubricBuilderPage", () => {
  it("lists rubrics", async () => {
    rubricsListMock.mockResolvedValueOnce(page([rubric]));
    criteriaListMock.mockResolvedValue(page<RubricCriterion>([]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    renderPage();

    expect(await screen.findByText("Essay Rubric")).toBeInTheDocument();
    expect(screen.getByText("Template")).toBeInTheDocument();
  });

  it("creates a rubric", async () => {
    rubricsListMock.mockResolvedValue(page<Rubric>([]));
    criteriaListMock.mockResolvedValue(page<RubricCriterion>([]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    rubricsCreateMock.mockResolvedValueOnce(rubric);
    renderPage();

    await screen.findByText("No rubrics found.");
    await userEvent.click(screen.getByRole("button", { name: "New Rubric" }));
    await userEvent.type(screen.getByLabelText(/^Name/), "Essay Rubric");
    await userEvent.type(screen.getByLabelText(/Total Marks/), "20");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(rubricsCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Essay Rubric", total_marks: 20 }),
      ),
    );
  });

  it("drills down into criteria and mark bands", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page([criterion]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Manage criteria for Essay Rubric" }));

    expect(await screen.findByText('Criteria for "Essay Rubric"')).toBeInTheDocument();
    await screen.findByText("Clarity");

    await userEvent.click(screen.getByRole("button", { name: "Manage mark bands for Clarity" }));

    expect(await screen.findByText('Mark Bands for "Clarity"')).toBeInTheDocument();
    expect(await screen.findByText("No mark bands found.")).toBeInTheDocument();
  });

  it("edits a rubric", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page<RubricCriterion>([]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    rubricsUpdateMock.mockResolvedValueOnce({ ...rubric, name: "Essay Rubric v2" });
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Edit Essay Rubric" }));

    const nameInput = await screen.findByLabelText(/^Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Essay Rubric v2");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(rubricsUpdateMock).toHaveBeenCalledWith(
        "rubric-1",
        expect.objectContaining({ name: "Essay Rubric v2" }),
      ),
    );
  });

  it("deletes a rubric", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page<RubricCriterion>([]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    rubricsRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Delete Essay Rubric" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(rubricsRemoveMock).toHaveBeenCalledWith("rubric-1"));
  });

  it("edits a criterion", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page([criterion]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    criteriaUpdateMock.mockResolvedValueOnce({ ...criterion, name: "Clarity v2" });
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Manage criteria for Essay Rubric" }));
    await screen.findByText("Clarity");

    await userEvent.click(screen.getByRole("button", { name: "Edit Clarity" }));
    const nameInput = await screen.findByLabelText(/^Name/);
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Clarity v2");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(criteriaUpdateMock).toHaveBeenCalledWith(
        "criterion-1",
        expect.objectContaining({ name: "Clarity v2" }),
      ),
    );
  });

  it("deletes a criterion", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page([criterion]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    criteriaRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Manage criteria for Essay Rubric" }));
    await screen.findByText("Clarity");

    await userEvent.click(screen.getByRole("button", { name: "Delete Clarity" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(criteriaRemoveMock).toHaveBeenCalledWith("criterion-1"));
  });

  it("sets a parent criterion selected from another existing criterion when creating a new criterion", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page([criterion, criterion2]));
    distributionsListMock.mockResolvedValue(page<MarkDistribution>([]));
    criteriaCreateMock.mockResolvedValueOnce({
      ...criterion,
      id: "criterion-3",
      name: "Sub-point",
      parent_criterion_id: "criterion-1",
    });
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Manage criteria for Essay Rubric" }));
    await screen.findByText("Clarity");
    await screen.findByText("Depth");

    await userEvent.click(screen.getByRole("button", { name: "New Criterion" }));
    await userEvent.selectOptions(screen.getByLabelText(/Parent Criterion/), "criterion-1");
    await userEvent.type(screen.getByLabelText(/^Name/), "Sub-point");
    const maxMarksInput = screen.getByLabelText(/Max Marks/);
    await userEvent.clear(maxMarksInput);
    await userEvent.type(maxMarksInput, "5");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(criteriaCreateMock).toHaveBeenCalledWith(
        expect.objectContaining({ parent_criterion_id: "criterion-1", name: "Sub-point" }),
      ),
    );
  });

  it("edits a mark band", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page([criterion]));
    distributionsListMock.mockResolvedValue(page([markDistribution]));
    distributionsUpdateMock.mockResolvedValueOnce({ ...markDistribution, band_name: "Outstanding" });
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Manage criteria for Essay Rubric" }));
    await screen.findByText("Clarity");
    await userEvent.click(screen.getByRole("button", { name: "Manage mark bands for Clarity" }));
    await screen.findByText("Excellent");

    await userEvent.click(screen.getByRole("button", { name: "Edit Excellent" }));
    const bandNameInput = await screen.findByLabelText(/Band Name/);
    await userEvent.clear(bandNameInput);
    await userEvent.type(bandNameInput, "Outstanding");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(distributionsUpdateMock).toHaveBeenCalledWith(
        "dist-1",
        expect.objectContaining({ band_name: "Outstanding" }),
      ),
    );
  });

  it("deletes a mark band", async () => {
    rubricsListMock.mockResolvedValue(page([rubric]));
    criteriaListMock.mockResolvedValue(page([criterion]));
    distributionsListMock.mockResolvedValue(page([markDistribution]));
    distributionsRemoveMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Essay Rubric");
    await userEvent.click(screen.getByRole("button", { name: "Manage criteria for Essay Rubric" }));
    await screen.findByText("Clarity");
    await userEvent.click(screen.getByRole("button", { name: "Manage mark bands for Clarity" }));
    await screen.findByText("Excellent");

    await userEvent.click(screen.getByRole("button", { name: "Delete Excellent" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(distributionsRemoveMock).toHaveBeenCalledWith("dist-1"));
  });
});
