import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { User } from "@/types/auth";

/**
 * Holds only the access token and the current user's identity/roles —
 * the minimum needed synchronously outside React (the axios interceptor
 * in `api/client.ts`, route guards). Deliberately has no thunks or API
 * calls of its own (see the module docstring in `api/client.ts` for why:
 * that keeps `store -> authSlice` free of any dependency on `api/`,
 * avoiding a `client.ts -> store -> authSlice -> api -> client.ts` cycle).
 * Everything else about a user (sessions, full profile fetch/update) is
 * server state and belongs in TanStack Query — see ADR-003.
 */
interface AuthState {
  user: User | null;
  accessToken: string | null;
  status: "idle" | "authenticated" | "unauthenticated";
}

const initialState: AuthState = {
  user: null,
  accessToken: null,
  status: "idle",
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials(state, action: PayloadAction<{ user: User; accessToken: string }>) {
      state.user = action.payload.user;
      state.accessToken = action.payload.accessToken;
      state.status = "authenticated";
    },
    updateUser(state, action: PayloadAction<User>) {
      state.user = action.payload;
    },
    clearCredentials(state) {
      state.user = null;
      state.accessToken = null;
      state.status = "unauthenticated";
    },
  },
});

export const { setCredentials, updateUser, clearCredentials } = authSlice.actions;
export default authSlice.reducer;
