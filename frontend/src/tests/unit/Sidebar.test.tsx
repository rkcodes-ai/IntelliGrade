import { configureStore } from "@reduxjs/toolkit";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Sidebar } from "@/components/layout/Sidebar";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import uiReducer from "@/store/slices/uiSlice";
import type { User } from "@/types/auth";

function renderSidebar(sidebarCollapsed: boolean, permissions: string[] = [], initialPath = "/dashboard") {
  const user: User | null =
    permissions.length > 0
      ? {
          id: "user-1",
          email: "user@example.com",
          username: "user",
          full_name: "Test User",
          phone: null,
          avatar_url: null,
          timezone: "UTC",
          language: "en",
          preferences: {},
          is_active: true,
          is_verified: true,
          roles: [],
          permissions,
          last_login_at: null,
          created_at: "2026-01-01T00:00:00Z",
        }
      : null;

  const store = configureStore({
    reducer: { ui: uiReducer, auth: authReducer, institution: institutionReducer },
    preloadedState: {
      ui: { theme: "light" as const, sidebarCollapsed },
      auth: { user, accessToken: user ? "token" : null, status: user ? ("authenticated" as const) : ("unauthenticated" as const) },
      institution: { currentInstitutionId: null },
    },
  });

  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Sidebar />
      </MemoryRouter>
    </Provider>,
  );
}

describe("Sidebar", () => {
  it("exposes an accessible name for nav links when expanded", () => {
    renderSidebar(false);
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("still exposes an accessible name for nav links when collapsed to icons-only", () => {
    // Regression test: the label used to be conditionally unmounted when
    // collapsed, leaving icon-only links with no accessible name at all.
    renderSidebar(true);
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("only shows workflow groups the user actually has permission for", () => {
    renderSidebar(false, ["official_exam_documents:read"]);
    expect(screen.getByText("Evaluation Packages")).toBeInTheDocument();
    expect(screen.queryByText("Teacher Review")).not.toBeInTheDocument();
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
  });

  it("hides every workflow group for a permission-less user but still shows Dashboard", () => {
    renderSidebar(false, []);
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.queryByText("Evaluation Packages")).not.toBeInTheDocument();
  });

  it("expands and collapses a group on click", async () => {
    const user = userEvent.setup();
    renderSidebar(false, ["official_exam_documents:read"]);

    const groupButton = screen.getByRole("button", { name: /Evaluation Packages/ });
    expect(groupButton).toHaveAttribute("aria-expanded", "true"); // expanded by default
    expect(screen.getByRole("link", { name: "Official Exam Documents" })).toBeInTheDocument();

    await user.click(groupButton);
    expect(groupButton).toHaveAttribute("aria-expanded", "false");
  });

  it("auto-expands the group containing the current route even before manual interaction", () => {
    // Academic & Assessment Setup is collapsed by default, but the current
    // route is one of its children — it must still open to reveal it.
    renderSidebar(false, ["institutions:read"], "/dashboard/institutions");
    const groupButton = screen.getByRole("button", { name: /Academic & Assessment Setup/ });
    expect(groupButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Institutions" })).toBeInTheDocument();
  });

  it("keeps every real route reachable by rendering all groups with at least one permitted item", () => {
    const allPermissions = [
      "official_exam_documents:read",
      "answer_scripts:read",
      "upload_jobs:read",
      "ocr_jobs:read",
      "answer_evaluations:read",
      "teacher_review_dashboard:read",
      "exam_results:read",
      "analytics:read",
      "reports:read",
      "ai_providers:read",
      "ai_configurations:read",
      "ocr_providers:read",
      "ocr_configurations:read",
      "institutions:read",
      "search:read",
      "notifications:read",
    ];
    renderSidebar(false, allPermissions);
    for (const label of [
      "Evaluation Packages",
      "Student Answer Scripts",
      "AI Evaluation",
      "Teacher Review",
      "Results",
      "Reports & Analytics",
      "Administration",
      "Academic & Assessment Setup",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});
