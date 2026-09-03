import { describe, expect, it } from "vitest";

import uiReducer, { setTheme, toggleSidebar, toggleTheme } from "@/store/slices/uiSlice";

describe("uiSlice", () => {
  const baseState = { theme: "light" as const, sidebarCollapsed: false };

  it("toggles theme between light and dark", () => {
    expect(uiReducer(baseState, toggleTheme()).theme).toBe("dark");
    expect(uiReducer({ ...baseState, theme: "dark" }, toggleTheme()).theme).toBe("light");
  });

  it("sets theme explicitly", () => {
    expect(uiReducer(baseState, setTheme("dark")).theme).toBe("dark");
  });

  it("toggles sidebar collapsed state", () => {
    expect(uiReducer(baseState, toggleSidebar()).sidebarCollapsed).toBe(true);
  });
});
