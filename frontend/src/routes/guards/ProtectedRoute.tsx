import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAppSelector } from "@/store";

/**
 * Requires authentication. Unauthenticated visitors are redirected to
 * `/login` with the attempted destination preserved in navigation state,
 * so `LoginPage` can send them back after a successful login.
 */
export function ProtectedRoute() {
  const status = useAppSelector((state) => state.auth.status);
  const location = useLocation();

  if (status === "unauthenticated") {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
