import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { ExamSchedulePage } from "@/pages/assessment/ExamSchedulePage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { Exam, ExamSchedule } from "@/types/assessment";
import type { Page } from "@/types/pagination";
import type { User } from "@/types/auth";

const { listMock, createMock, updateMock, removeMock, examsListMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  removeMock: vi.fn(),
  examsListMock: vi.fn(),
}));
vi.mock("@/api/examSchedules", () => ({
  examSchedulesApi: {
    list: listMock,
    listDeleted: vi.fn(),
    get: vi.fn(),
    create: createMock,
    update: updateMock,
    remove: removeMock,
    restore: vi.fn(),
  },
}));
vi.mock("@/api/exams", () => ({
  examsApi: {
    list: examsListMock,
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
    "exam_schedules:create",
    "exam_schedules:read",
    "exam_schedules:update",
    "exam_schedules:delete",
  ],
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

const exam: Exam = {
  id: "exam-1",
  institution_id: "inst-1",
  assessment_id: "assessment-1",
  section_id: "section-1",
  name: "Midterm Physics",
  exam_date: "2026-07-20",
  is_active: true,
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const schedule: ExamSchedule = {
  id: "schedule-1",
  institution_id: "inst-1",
  exam_id: "exam-1",
  room_id: "Room-101",
  start_time: "2026-07-20T09:00:00.000Z",
  end_time: "2026-07-20T11:00:00.000Z",
  invigilator_user_id: "user-99",
  is_active: true,
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
            <ExamSchedulePage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("ExamSchedulePage", () => {
  it("lists exam schedules for the current institution", async () => {
    examsListMock.mockResolvedValue(page([exam]));
    listMock.mockResolvedValueOnce(page([schedule]));
    renderPage();
    expect(await screen.findByText("Midterm Physics")).toBeInTheDocument();
    expect(screen.getByText("Room-101")).toBeInTheDocument();
    expect(screen.getByText("user-99")).toBeInTheDocument();
  });

  it("creates an exam schedule", async () => {
    examsListMock.mockResolvedValue(page([exam]));
    listMock.mockResolvedValue(page([]));
    createMock.mockResolvedValueOnce(schedule);
    renderPage();

    await screen.findByText("No exam schedules found.");
    await userEvent.click(screen.getByRole("button", { name: "New Exam Schedule" }));

    await userEvent.selectOptions(await screen.findByLabelText(/^Exam/), "exam-1");
    await userEvent.type(screen.getByLabelText(/^Room ID/), "Room-101");
    const startInput = screen.getByLabelText(/^Start Time/);
    const endInput = screen.getByLabelText(/^End Time/);
    await userEvent.type(startInput, "2026-07-20T09:00");
    await userEvent.type(endInput, "2026-07-20T11:00");
    await userEvent.type(screen.getByLabelText(/^Invigilator User ID/), "user-99");

    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          exam_id: "exam-1",
          room_id: "Room-101",
          invigilator_user_id: "user-99",
        }),
      ),
    );
  });

  it("deletes an exam schedule after confirmation", async () => {
    examsListMock.mockResolvedValue(page([exam]));
    listMock.mockResolvedValue(page([schedule]));
    removeMock.mockResolvedValueOnce(undefined);
    renderPage();

    await screen.findByText("Midterm Physics");
    await userEvent.click(screen.getByRole("button", { name: "Delete Midterm Physics" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(removeMock).toHaveBeenCalledWith("schedule-1"));
  });
});
