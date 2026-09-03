import { useEffect, type ReactNode } from "react";

import { useAppSelector } from "@/store";

/**
 * Applies the current Redux `ui.theme` value to `<html class="dark">` and
 * persists the choice. Toggle theme via `dispatch(toggleTheme())` from
 * `store/slices/uiSlice`.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useAppSelector((state) => state.ui.theme);

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("intelligrade-theme", theme);
  }, [theme]);

  return children;
}
