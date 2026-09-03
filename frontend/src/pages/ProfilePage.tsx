import { useEffect, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { changePassword } from "@/api/auth";
import { getMe, updateMe } from "@/api/users";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { DetailLoading } from "@/components/common/DetailState";
import { PageHeader } from "@/components/common/PageHeader";
import { extractErrorMessage } from "@/lib/errors";
import { useAppDispatch } from "@/store";
import { updateUser } from "@/store/slices/authSlice";

const profileSchema = z.object({
  fullName: z.string().min(1, "Name is required."),
  phone: z.string().optional(),
  timezone: z.string().min(1, "Timezone is required."),
  language: z.string().min(1, "Language is required."),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "Enter your current password."),
    newPassword: z.string().min(8, "At least 8 characters."),
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  });

type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;

export function ProfilePage() {
  const dispatch = useAppDispatch();
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery({ queryKey: ["me"], queryFn: getMe });

  const profileForm = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { fullName: "", phone: "", timezone: "UTC", language: "en" },
  });

  useEffect(() => {
    if (user) {
      profileForm.reset({
        fullName: user.full_name,
        phone: user.phone ?? "",
        timezone: user.timezone,
        language: user.language,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resets only when the fetched user changes
  }, [user]);

  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const profileSuccessTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const updateProfileMutation = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      updateMe({
        full_name: values.fullName,
        phone: values.phone,
        timezone: values.timezone,
        language: values.language,
      }),
    onSuccess: (updated) => {
      dispatch(updateUser(updated));
      queryClient.setQueryData(["me"], updated);
      setProfileError(null);
      setProfileSuccess(true);
      clearTimeout(profileSuccessTimeout.current);
      profileSuccessTimeout.current = setTimeout(() => setProfileSuccess(false), 3000);
    },
    onError: (error) => setProfileError(extractErrorMessage(error)),
  });

  const passwordForm = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
  });
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const passwordSuccessTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const changePasswordMutation = useMutation({
    mutationFn: (values: ChangePasswordFormValues) =>
      changePassword({
        current_password: values.currentPassword,
        new_password: values.newPassword,
      }),
    onSuccess: () => {
      setPasswordError(null);
      setPasswordSuccess(true);
      passwordForm.reset();
      clearTimeout(passwordSuccessTimeout.current);
      passwordSuccessTimeout.current = setTimeout(() => setPasswordSuccess(false), 3000);
    },
    onError: (error) => setPasswordError(extractErrorMessage(error)),
  });

  useEffect(
    () => () => {
      clearTimeout(profileSuccessTimeout.current);
      clearTimeout(passwordSuccessTimeout.current);
    },
    [],
  );

  if (isLoading) {
    return <DetailLoading />;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Profile" description="Manage your personal information and password." />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Personal information</CardTitle>
          <CardDescription>Update your name, phone, timezone, and language.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={profileForm.handleSubmit((values) => updateProfileMutation.mutate(values))}
            className="flex flex-col gap-4"
            noValidate
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fullName">Full name</Label>
              <Input id="fullName" {...profileForm.register("fullName")} />
              {profileForm.formState.errors.fullName && (
                <p className="text-sm text-destructive">
                  {profileForm.formState.errors.fullName.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" {...profileForm.register("phone")} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="timezone">Timezone</Label>
                <Input id="timezone" {...profileForm.register("timezone")} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="language">Language</Label>
                <Input id="language" {...profileForm.register("language")} />
              </div>
            </div>

            {profileError && (
              <p role="alert" className="text-sm text-destructive">
                {profileError}
              </p>
            )}
            {profileSuccess && (
              <p className="flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" /> Profile updated.
              </p>
            )}

            <Button type="submit" disabled={updateProfileMutation.isPending} className="self-start">
              {updateProfileMutation.isPending && <Spinner className="h-4 w-4" />}
              Save changes
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Change password</CardTitle>
          <CardDescription>Signs you out of every other session.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={passwordForm.handleSubmit((values) => changePasswordMutation.mutate(values))}
            className="flex flex-col gap-4"
            noValidate
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="currentPassword">Current password</Label>
              <Input
                id="currentPassword"
                type="password"
                autoComplete="current-password"
                {...passwordForm.register("currentPassword")}
              />
              {passwordForm.formState.errors.currentPassword && (
                <p className="text-sm text-destructive">
                  {passwordForm.formState.errors.currentPassword.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                autoComplete="new-password"
                {...passwordForm.register("newPassword")}
              />
              {passwordForm.formState.errors.newPassword && (
                <p className="text-sm text-destructive">
                  {passwordForm.formState.errors.newPassword.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirmPassword">Confirm new password</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                {...passwordForm.register("confirmPassword")}
              />
              {passwordForm.formState.errors.confirmPassword && (
                <p className="text-sm text-destructive">
                  {passwordForm.formState.errors.confirmPassword.message}
                </p>
              )}
            </div>

            {passwordError && (
              <p role="alert" className="text-sm text-destructive">
                {passwordError}
              </p>
            )}
            {passwordSuccess && (
              <p className="flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" /> Password changed.
              </p>
            )}

            <Button
              type="submit"
              disabled={changePasswordMutation.isPending}
              variant="secondary"
              className="self-start"
            >
              {changePasswordMutation.isPending && <Spinner className="h-4 w-4" />}
              Change password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
