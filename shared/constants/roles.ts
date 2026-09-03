/**
 * Canonical role identifiers shared across frontend and (conceptually) backend.
 * Backend mirrors this in `backend/app/core/constants.py` — keep both in sync.
 */
export const ROLES = {
  SUPER_ADMIN: "super_admin",
  INSTITUTION_ADMIN: "institution_admin",
  TEACHER: "teacher",
  STUDENT: "student",
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];
