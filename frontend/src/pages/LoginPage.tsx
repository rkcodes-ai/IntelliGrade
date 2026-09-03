import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { login as loginRequest } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { extractErrorMessage } from "@/lib/errors";
import { useAppDispatch } from "@/store";
import { setCredentials } from "@/store/slices/authSlice";

const loginSchema = z.object({
  identifier: z.string().min(1, "Enter your username or email."),
  password: z.string().min(1, "Enter your password."),
  rememberMe: z.boolean(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifier: "", password: "", rememberMe: false },
  });

  const redirectTo =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/dashboard";

  async function onSubmit(values: LoginFormValues) {
    setServerError(null);
    try {
      const response = await loginRequest({
        identifier: values.identifier,
        password: values.password,
        remember_me: values.rememberMe,
      });
      dispatch(setCredentials({ user: response.user, accessToken: response.access_token }));
      navigate(redirectTo, { replace: true });
    } catch (error) {
      setServerError(extractErrorMessage(error));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="identifier">Username or email</Label>
        <Input
          id="identifier"
          autoComplete="username"
          aria-invalid={!!errors.identifier}
          aria-describedby={errors.identifier ? "identifier-error" : undefined}
          {...register("identifier")}
        />
        {errors.identifier && (
          <p id="identifier-error" className="text-sm text-destructive">
            {errors.identifier.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.password}
          aria-describedby={errors.password ? "password-error" : undefined}
          {...register("password")}
        />
        {errors.password && (
          <p id="password-error" className="text-sm text-destructive">
            {errors.password.message}
          </p>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border"
          {...register("rememberMe")}
        />
        Remember me
      </label>

      {serverError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          {serverError}
        </div>
      )}

      <Button type="submit" disabled={isSubmitting} className="mt-2">
        {isSubmitting && <Spinner className="h-4 w-4" />}
        Sign in
      </Button>

      <Link
        to="/forgot-password"
        className="text-center text-sm text-muted-foreground hover:text-foreground hover:underline"
      >
        Forgot your password?
      </Link>
    </form>
  );
}
