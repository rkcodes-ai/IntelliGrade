import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ResetPasswordPage } from "@/pages/ResetPasswordPage";

const { resetPasswordMock } = vi.hoisted(() => ({ resetPasswordMock: vi.fn() }));
vi.mock("@/api/auth", () => ({ resetPassword: resetPasswordMock }));

function renderPage(initialPath = "/reset-password?token=abc123") {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/forgot-password" element={<div>Forgot password page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ResetPasswordPage", () => {
  it("shows a missing-token message when there is no token in the URL", () => {
    renderPage("/reset-password");
    expect(screen.getByText(/missing its token/i)).toBeInTheDocument();
  });

  it("rejects a weak new password", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText("New password"), "weak");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "weak");
    await userEvent.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByText("At least 8 characters.")).toBeInTheDocument();
    expect(resetPasswordMock).not.toHaveBeenCalled();
  });

  it("rejects mismatched passwords", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText("New password"), "StrongPass9!");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "DifferentPass9!");
    await userEvent.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByText("Passwords do not match.")).toBeInTheDocument();
    expect(resetPasswordMock).not.toHaveBeenCalled();
  });

  it("submits the token and new password, then redirects to login", async () => {
    resetPasswordMock.mockResolvedValueOnce({ message: "ok" });
    renderPage();

    await userEvent.type(screen.getByLabelText("New password"), "StrongPass9!");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "StrongPass9!");
    await userEvent.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(resetPasswordMock).toHaveBeenCalledWith({
      token: "abc123",
      new_password: "StrongPass9!",
    });
  });
});
