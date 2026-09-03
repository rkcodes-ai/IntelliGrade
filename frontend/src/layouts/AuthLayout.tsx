import { Outlet } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Structural shell for auth-adjacent pages (login, register, reset password).
 * No auth forms/logic live here yet — the Authentication module renders
 * its pages through this layout via nested routes (see `routes/index.tsx`).
 */
export function AuthLayout() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-center">IntelliGrade</CardTitle>
        </CardHeader>
        <CardContent>
          <Outlet />
        </CardContent>
      </Card>
    </div>
  );
}
