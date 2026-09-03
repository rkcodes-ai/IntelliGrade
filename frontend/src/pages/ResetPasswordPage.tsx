import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { resetPassword } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { extractErrorMessage } from "@/lib/errors";

// Mirrors the backend's enterprise password policy — see
// backend/app/core/password_policy.py. Kept in sync manually; both sides
// must independently enforce it (client-side for UX, server-side for
// security, per docs/security.md).
const passwordPolicySchema = z
  .string()
  .min(8, "At least 8 characters.")
  .max(72, "At most 72 bytes.")
  .regex(/[A-Z]/, "At least one uppercase letter.")
  .regex(/[a-z]/, "At least one lowercase letter.")
  .regex(/\d/, "At least one number.")
  .regex(/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?~`]/, "At least one special character.");

const resetPasswordSchema = z
  .object({
    newPassword: passwordPolicySchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  });

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { newPassword: "", confirmPassword: "" },
  });

  async function onSubmit(values: ResetPasswordFormValues) {
    if (!token) return;
    setServerError(null);
    try {
      await resetPassword({ token, new_password: values.newPassword });
      navigate("/login", { replace: true });
    } catch (error) {
      setServerError(extractErrorMessage(error));
    }
  }

  if (!token) {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <p className="text-sm text-destructive">
          This reset link is missing its token. Request a new one.
        </p>
        <Link to="/forgot-password" className="text-sm font-medium text-primary hover:underline">
          Request a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="newPassword">New password</Label>
        <Input
          id="newPassword"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.newPassword}
          aria-describedby={errors.newPassword ? "newPassword-error" : undefined}
          {...register("newPassword")}
        />
        {errors.newPassword && (
          <p id="newPassword-error" className="text-sm text-destructive">
            {errors.newPassword.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="confirmPassword">Confirm new password</Label>
        <Input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirmPassword}
          aria-describedby={errors.confirmPassword ? "confirmPassword-error" : undefined}
          {...register("confirmPassword")}
        />
        {errors.confirmPassword && (
          <p id="confirmPassword-error" className="text-sm text-destructive">
            {errors.confirmPassword.message}
          </p>
        )}
      </div>

      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting && <Spinner className="h-4 w-4" />}
        Reset password
      </Button>
    </form>
  );
}
