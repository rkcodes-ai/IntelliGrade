import { afterEach, beforeEach, describe, expect, it } from "vitest";

import institutionReducer, { setCurrentInstitution } from "@/store/slices/institutionSlice";

describe("institutionSlice", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("sets the current institution id and persists it to localStorage", () => {
    const state = institutionReducer({ currentInstitutionId: null }, setCurrentInstitution("inst-1"));
    expect(state.currentInstitutionId).toBe("inst-1");
    expect(window.localStorage.getItem("intelligrade-current-institution")).toBe("inst-1");
  });

  it("clears the current institution id and removes it from localStorage", () => {
    window.localStorage.setItem("intelligrade-current-institution", "inst-1");
    const state = institutionReducer(
      { currentInstitutionId: "inst-1" },
      setCurrentInstitution(null),
    );
    expect(state.currentInstitutionId).toBeNull();
    expect(window.localStorage.getItem("intelligrade-current-institution")).toBeNull();
  });
});
