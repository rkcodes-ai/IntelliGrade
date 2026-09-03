import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { MarkSchemeVerificationPage } from "@/pages/ocr/MarkSchemeVerificationPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { User } from "@/types/auth";
import type { MarkSchemeExpansionResponse, MarkSchemeRange } from "@/types/officialExam";
import type { Page } from "@/types/pagination";

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { listMock, updateMock, verifyMock, expandMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  updateMock: vi.fn(),
  verifyMock: vi.fn(),
  expandMock: vi.fn(),
}));
vi.mock("@/api/markSchemeRanges", () => ({
  listMarkSchemeRanges: listMock,
  getMarkSchemeRange: vi.fn(),
  updateMarkSchemeRange: updateMock,
  verifyMarkSchemeRange: verifyMock,
  expandMarkScheme: expandMock,
}));

function makeUser(permissions: string[]): User {
  return {
    id: "user-1",
    email: "teacher@example.com",
    username: "teacher",
    full_name: "Teacher",
    phone: null,
    avatar_url: null,
    timezone: "UTC",
    language: "en",
    preferences: {},
    is_active: true,
    is_verified: true,
    roles: ["teacher"],
    permissions,
    last_login_at: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

function makeRange(overrides: Partial<MarkSchemeRange> = {}): MarkSchemeRange {
  return {
    id: "range-1",
    institution_id: "inst-1",
    document_id: "document-1",
    question_range_start: "1",
    question_range_end: "5",
    marks_per_question: "10",
    display_order: 0,
    verification_status: "pending",
    verified_by: null,
    verified_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function page(items: MarkSchemeRange[]): Page<MarkSchemeRange> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1 };
}

function renderPage(permissions: string[], documentId = "document-1") {
  const store = configureStore({
    reducer: { auth: authReducer, institution: institutionReducer },
    preloadedState: {
      auth: { user: makeUser(permissions), accessToken: "token", status: "authenticated" as const },
      institution: { currentInstitutionId: "inst-1" },
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/dashboard/official-exam-documents/${documentId}/mark-scheme`]}>
          <ToastProvider>
            <Routes>
              <Route
                path="/dashboard/official-exam-documents/:documentId/mark-scheme"
                element={<MarkSchemeVerificationPage />}
              />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("MarkSchemeVerificationPage", () => {
  it("shows a loading state before data resolves", async () => {
    let resolveList: (value: Page<MarkSchemeRange>) => void = () => {};
    listMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );
    renderPage(["mark_scheme_ranges:update", "mark_scheme_ranges:verify"]);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    resolveList(page([]));
    await screen.findByText("No mark scheme ranges found for this document.");
  });

  it("lists mark scheme ranges filtered by the route's documentId", async () => {
    listMock.mockResolvedValueOnce(page([makeRange()]));
    renderPage(["mark_scheme_ranges:update", "mark_scheme_ranges:verify"]);

    expect(await screen.findByText("pending")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ document_id: "document-1" }));
  });

  it("verifies a mark scheme range and shows a success toast", async () => {
    listMock.mockResolvedValue(page([makeRange()]));
    verifyMock.mockResolvedValueOnce(makeRange({ verification_status: "verified" }));
    renderPage(["mark_scheme_ranges:update", "mark_scheme_ranges:verify"]);

    await screen.findByText("pending");
    await userEvent.click(screen.getByRole("button", { name: "Verify range 1-5" }));

    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith("range-1"));
    expect(await screen.findByText("Mark scheme range verified.")).toBeInTheDocument();
  });

  it("edits a mark scheme range via the form dialog", async () => {
    listMock.mockResolvedValue(page([makeRange()]));
    updateMock.mockResolvedValueOnce(makeRange({ marks_per_question: "12" }));
    renderPage(["mark_scheme_ranges:update", "mark_scheme_ranges:verify"]);

    await screen.findByText("pending");
    await userEvent.click(screen.getByRole("button", { name: "Edit range 1-5" }));

    const marksInput = await screen.findByLabelText(/^Marks per Question/);
    await userEvent.clear(marksInput);
    await userEvent.type(marksInput, "12");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("range-1", {
        question_range_start: "1",
        question_range_end: "5",
        marks_per_question: 12,
      }),
    );
    expect(await screen.findByText("Mark scheme range updated.")).toBeInTheDocument();
  });

  it("hides the verify button when the permission is absent", async () => {
    listMock.mockResolvedValueOnce(page([makeRange()]));
    renderPage(["mark_scheme_ranges:update"]);

    await screen.findByText("pending");
    expect(screen.queryByRole("button", { name: "Verify range 1-5" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit range 1-5" })).toBeInTheDocument();
  });

  it("previews the live mark-scheme expansion, rendering computed marks and warnings", async () => {
    listMock.mockResolvedValue(page([makeRange()]));
    const expansionResponse: MarkSchemeExpansionResponse = {
      marks_by_question: { "1": "10", "2": "10", "3": "10" },
      warnings: ["Question 4 has no matching range."],
    };
    expandMock.mockResolvedValueOnce(expansionResponse);
    renderPage(["mark_scheme_ranges:update", "mark_scheme_ranges:verify"]);

    await screen.findByText("pending");
    await userEvent.click(screen.getByRole("button", { name: "Preview Expansion" }));

    await waitFor(() => expect(expandMock).toHaveBeenCalledWith("document-1"));
    expect(await screen.findByText("Expansion Preview")).toBeInTheDocument();
    expect(screen.getByText("Question 4 has no matching range.")).toBeInTheDocument();
    // Question numbers 1-3 and their marks from the mocked expansion response
    // — scoped to the expansion table since the verification step nav also
    // renders bare numerals ("1"/"2"/"3") for its own steps.
    // CardTitle -> CardHeader div -> Card div (the whole expansion preview card).
    const expansionHeading = screen.getByText("Expansion Preview");
    const expansionCard = expansionHeading.parentElement?.parentElement as HTMLElement;
    expect(within(expansionCard).getAllByText("10").length).toBeGreaterThanOrEqual(3);
    expect(within(expansionCard).getByText("2")).toBeInTheDocument();
    expect(within(expansionCard).getByText("3")).toBeInTheDocument();
  });
});
