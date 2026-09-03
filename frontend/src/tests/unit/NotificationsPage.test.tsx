import { configureStore } from "@reduxjs/toolkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/context/ToastProvider";
import { NotificationsPage } from "@/pages/ocr/NotificationsPage";
import authReducer from "@/store/slices/authSlice";
import institutionReducer from "@/store/slices/institutionSlice";
import type { NotificationEvent } from "@/types/teacherReview";
import type { User } from "@/types/auth";

const { listMock, unreadCountMock, markReadMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  unreadCountMock: vi.fn(),
  markReadMock: vi.fn(),
}));
vi.mock("@/api/notifications", () => ({
  listMyNotifications: listMock,
  getUnreadNotificationCount: unreadCountMock,
  markNotificationRead: markReadMock,
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

function makeNotification(overrides: Partial<NotificationEvent> = {}): NotificationEvent {
  return {
    id: "notif-1",
    institution_id: "inst-1",
    recipient_user_id: "user-1",
    event_type: "result_published",
    payload: { exam_session_id: "session-1" },
    is_read: false,
    read_at: null,
    created_at: "2026-01-15T10:30:00Z",
    updated_at: "2026-01-15T10:30:00Z",
    ...overrides,
  };
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
        <MemoryRouter initialEntries={["/dashboard/notifications"]}>
          <ToastProvider>
            <NotificationsPage />
          </ToastProvider>
        </MemoryRouter>
      </Provider>
    </QueryClientProvider>,
  );
}

describe("NotificationsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders notifications with a humanized event type and formatted date", async () => {
    listMock.mockResolvedValueOnce([
      makeNotification({ event_type: "result_published", created_at: "2026-01-15T10:30:00Z" }),
    ]);
    unreadCountMock.mockResolvedValueOnce(1);
    renderPage();

    expect(await screen.findByText("result published")).toBeInTheDocument();
    expect(
      screen.getByText(new Date("2026-01-15T10:30:00Z").toLocaleString()),
    ).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(false);
  });

  it("shows Mark as read only for unread notifications, and marks it read on click", async () => {
    listMock.mockResolvedValue([
      makeNotification({ id: "notif-unread", is_read: false, event_type: "unread_event" }),
      makeNotification({ id: "notif-read", is_read: true, event_type: "read_event", read_at: "2026-01-16T00:00:00Z" }),
    ]);
    unreadCountMock.mockResolvedValue(1);
    markReadMock.mockResolvedValueOnce(
      makeNotification({ id: "notif-unread", is_read: true, event_type: "unread_event" }),
    );
    renderPage();

    await screen.findByText("unread event");
    expect(screen.getByText("read event")).toBeInTheDocument();

    const markReadButtons = screen.getAllByRole("button", { name: "Mark as read" });
    expect(markReadButtons).toHaveLength(1);

    await userEvent.click(markReadButtons[0]);

    await waitFor(() => expect(markReadMock).toHaveBeenCalledWith("notif-unread"));
    expect(await screen.findByText("Notification marked as read.")).toBeInTheDocument();
    // refetch triggered by invalidation
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
  });

  it("shows an error toast when marking as read fails", async () => {
    listMock.mockResolvedValue([makeNotification({ id: "notif-unread", is_read: false })]);
    unreadCountMock.mockResolvedValue(1);
    markReadMock.mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { error: { message: "Could not mark notification as read." } } },
    });
    renderPage();

    const markReadButton = await screen.findByRole("button", { name: "Mark as read" });
    await userEvent.click(markReadButton);

    expect(await screen.findByText("Could not mark notification as read.")).toBeInTheDocument();
  });

  it("toggles to Unread Only and calls listMyNotifications(true)", async () => {
    listMock.mockResolvedValue([]);
    unreadCountMock.mockResolvedValue(0);
    renderPage();

    await waitFor(() => expect(listMock).toHaveBeenCalledWith(false));

    await userEvent.click(screen.getByRole("button", { name: "Unread Only" }));

    await waitFor(() => expect(listMock).toHaveBeenCalledWith(true));
  });

  it("shows the empty-state message when there are no notifications", async () => {
    listMock.mockResolvedValueOnce([]);
    unreadCountMock.mockResolvedValueOnce(0);
    renderPage();

    expect(await screen.findByText("No notifications yet.")).toBeInTheDocument();
  });
});
