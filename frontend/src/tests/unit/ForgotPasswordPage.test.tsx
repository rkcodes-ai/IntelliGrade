import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";

const { forgotPasswordMock } = vi.hoisted(() => ({ forgotPasswordMock: vi.fn() }));
vi.mock("@/api/auth", () => ({ forgotPassword: forgotPasswordMock }));

function renderPage() {
  render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

describe("ForgotPasswordPage", () => {
  it("validates the email field", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(forgotPasswordMock).not.toHaveBeenCalled();
  });

  it("shows a generic success message regardless of whether the email is registered", async () => {
    forgotPasswordMock.mockResolvedValueOnce({ message: "ok" });
    renderPage();

    await userEvent.type(screen.getByLabelText("Email"), "someone@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(
      await screen.findByText("If that email is registered, a password reset link has been sent."),
    ).toBeInTheDocument();
    expect(forgotPasswordMock).toHaveBeenCalledWith({ email: "someone@example.com" });
  });
});
