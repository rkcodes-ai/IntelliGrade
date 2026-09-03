import { Navigate, Outlet } from "react-router-dom";

import { useAppSelector } from "@/store";

/**
 * Restricts a route subtree to callers holding at least one of
 * `allowedRoles`. Must be nested under `ProtectedRoute` (assumes
 * `user` is already populated) — renders `/unauthorized` otherwise.
 */
export function RoleGuard({ allowedRoles }: { allowedRoles: string[] }) {
  const user = useAppSelector((state) => state.auth.user);
  const hasRole = user ? allowedRoles.some((role) => user.roles.includes(role)) : false;

  if (!hasRole) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
}
