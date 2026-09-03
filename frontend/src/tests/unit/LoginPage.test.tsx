import { configureStore } from "@reduxjs/toolkit";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LoginPage } from "@/pages/LoginPage";
import authReducer from "@/store/slices/authSlice";
import uiReducer from "@/store/slices/uiSlice";

const { loginMock } = vi.hoisted(() => ({ loginMock: vi.fn() }));
vi.mock("@/api/auth", () => ({ login: loginMock }));

function renderLoginPage() {
  const store = configureStore({ reducer: { ui: uiReducer, auth: authReducer } });
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>Dashboard page</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

describe("LoginPage", () => {
  it("shows validation errors when submitted empty", async () => {
    renderLoginPage();
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter your username or email.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("submits credentials and navigates to the dashboard on success", async () => {
    loginMock.mockResolvedValueOnce({
      access_token: "token-123",
      token_type: "bearer",
      expires_in: 1800,
      user: {
        id: "user-1",
        email: "alice@example.com",
        username: "alice",
        full_name: "Alice",
        phone: null,
        avatar_url: null,
        timezone: "UTC",
        language: "en",
        preferences: {},
        is_active: true,
        is_verified: false,
        roles: ["student"],
        permissions: [],
        last_login_at: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    });

    const store = renderLoginPage();

    await userEvent.type(screen.getByLabelText("Username or email"), "alice");
    await userEvent.type(screen.getByLabelText("Password"), "CorrectHorse9!");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByText("Dashboard page")).toBeInTheDocument());
    expect(loginMock).toHaveBeenCalledWith({
      identifier: "alice",
      password: "CorrectHorse9!",
      remember_me: false,
    });
    expect(store.getState().auth.status).toBe("authenticated");
    expect(store.getState().auth.accessToken).toBe("token-123");
  });

  it("shows the server error message on failed login", async () => {
    loginMock.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        data: { error: { code: "unauthorized", message: "Incorrect username/email or password." } },
      },
    });

    renderLoginPage();

    await userEvent.type(screen.getByLabelText("Username or email"), "alice");
    await userEvent.type(screen.getByLabelText("Password"), "WrongPassword1!");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect username/email or password.",
    );
  });
});
