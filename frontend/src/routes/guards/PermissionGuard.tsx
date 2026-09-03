import { Navigate, Outlet } from "react-router-dom";

import { useAppSelector } from "@/store";

/**
 * Restricts a route subtree to callers holding *all* of
 * `requiredPermissions`. Prefer this over `RoleGuard` for most routes —
 * it stays correct even if role→permission grants change later, since the
 * route never hardcodes a role name (mirrors the backend's
 * `require_permissions` — see `docs/rbac.md`).
 */
export function PermissionGuard({ requiredPermissions }: { requiredPermissions: string[] }) {
  const user = useAppSelector((state) => state.auth.user);
  const hasAllPermissions = user
    ? requiredPermissions.every((permission) => user.permissions.includes(permission))
    : false;

  if (!hasAllPermissions) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
}
