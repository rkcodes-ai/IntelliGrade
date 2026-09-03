/**
 * Current-institution (tenant) selection — client/session state only, same
 * category as `uiSlice`'s theme/sidebar (persisted to localStorage, not
 * server data). The actual list of institutions a user may select from is
 * server state and belongs in TanStack Query (see `api/institutions.ts`'s
 * `listMyInstitutions`), matching the `authSlice` precedent of keeping
 * Redux free of server-fetched data.
 */
import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface InstitutionState {
  currentInstitutionId: string | null;
}

const STORAGE_KEY = "intelligrade-current-institution";

function getInitialInstitutionId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

const initialState: InstitutionState = {
  currentInstitutionId: getInitialInstitutionId(),
};

const institutionSlice = createSlice({
  name: "institution",
  initialState,
  reducers: {
    setCurrentInstitution(state, action: PayloadAction<string | null>) {
      state.currentInstitutionId = action.payload;
      if (typeof window !== "undefined") {
        if (action.payload) {
          window.localStorage.setItem(STORAGE_KEY, action.payload);
        } else {
          window.localStorage.removeItem(STORAGE_KEY);
        }
      }
    },
  },
});

export const { setCurrentInstitution } = institutionSlice.actions;
export default institutionSlice.reducer;
