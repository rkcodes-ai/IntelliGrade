import { LogOut, Menu, Moon, Sun, User } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { logout as logoutRequest } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { InstitutionSwitcher } from "@/components/layout/InstitutionSwitcher";
import { useToast } from "@/context/ToastProvider";
import { toggleSidebar, toggleTheme } from "@/store/slices/uiSlice";
import { clearCredentials } from "@/store/slices/authSlice";
import { useAppDispatch, useAppSelector } from "@/store";

/** Dashboard top bar: sidebar/theme toggles, current user, and sign-out. */
export function Topbar() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { toast } = useToast();
  const theme = useAppSelector((state) => state.ui.theme);
  const user = useAppSelector((state) => state.auth.user);

  async function handleLogout() {
    try {
      await logoutRequest();
    } catch {
      // Even if the server call fails (e.g. network blip), clear local
      // credentials so the user isn't stuck appearing signed in.
    } finally {
      dispatch(clearCredentials());
      toast("Signed out.", "info");
      navigate("/login", { replace: true });
    }
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Toggle sidebar"
        onClick={() => dispatch(toggleSidebar())}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <span className="text-sm font-medium">IntelliGrade</span>

      <InstitutionSwitcher />

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
          onClick={() => dispatch(toggleTheme())}
        >
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>

        <Button variant="ghost" size="icon" aria-label="Your profile" asChild>
          <Link to="/dashboard/profile">
            <User className="h-5 w-5" />
          </Link>
        </Button>

        <Button
          variant="ghost"
          size="icon"
          aria-label="Sign out"
          onClick={() => void handleLogout()}
        >
          <LogOut className="h-5 w-5" />
        </Button>

        {user && (
          <span className="hidden text-sm text-muted-foreground sm:inline">{user.username}</span>
        )}
      </div>
    </header>
  );
}
