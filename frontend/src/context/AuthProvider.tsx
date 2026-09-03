import { useEffect, useState, type ReactNode } from "react";

import { apiClient } from "@/api/client";
import { LoadingScreen } from "@/components/common/LoadingScreen";
import { useAppDispatch } from "@/store";
import { clearCredentials, setCredentials } from "@/store/slices/authSlice";
import type { TokenResponse } from "@/types/auth";

/**
 * Restores a session on page load/refresh. The Redux auth slice is
 * in-memory only (see `docs/authentication-guide.md` on why the access
 * token is never persisted to localStorage/sessionStorage — XSS blast
 * radius), so a hard reload loses it even though the httpOnly refresh
 * cookie the browser holds is still valid. This provider silently attempts
 * `/auth/refresh` once on mount to trade that cookie for a new access
 * token before rendering any route — a failure just means "not logged in,"
 * not an error, so it's handled quietly rather than surfaced to the user.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const dispatch = useAppDispatch();
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const { data } = await apiClient.post<TokenResponse>("/auth/refresh");
        if (!cancelled) {
          dispatch(setCredentials({ user: data.user, accessToken: data.access_token }));
        }
      } catch {
        if (!cancelled) {
          dispatch(clearCredentials());
        }
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs exactly once, intentionally
  }, []);

  if (isBootstrapping) {
    return <LoadingScreen label="Loading your session…" />;
  }

  return children;
}
