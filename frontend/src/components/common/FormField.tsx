import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

interface FormFieldProps {
  htmlFor: string;
  label: string;
  error?: string;
  children: ReactNode;
  required?: boolean;
}

/** Label + control + validation-error slot, matching the existing hand-wired pattern in ProfilePage.tsx. */
export function FormField({ htmlFor, label, error, children, required = false }: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>
        {label}
        {required && <span className="text-destructive"> *</span>}
      </Label>
      {children}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
