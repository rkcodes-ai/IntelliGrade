/**
 * Types mirroring the backend's IAM schemas (`backend/app/schemas/`)
 * field-for-field, including casing. The API returns snake_case JSON (the
 * Pydantic schemas have no camelCase alias generator) — these types match
 * the wire format exactly rather than introducing a case-conversion layer
 * this project doesn't otherwise have. See `docs/api-standards.md`.
 */

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  phone: string | null;
  avatar_url: string | null;
  timezone: string;
  language: string;
  preferences: Record<string, unknown>;
  is_active: boolean;
  is_verified: boolean;
  roles: string[];
  permissions: string[];
  last_login_at: string | null;
  created_at: string;
}

export interface LoginRequest {
  identifier: string;
  password: string;
  remember_me: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UserProfileUpdate {
  full_name?: string;
  phone?: string;
  avatar_url?: string;
  timezone?: string;
  language?: string;
  preferences?: Record<string, unknown>;
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

export interface Permission {
  id: string;
  code: string;
  resource: string;
  action: string;
  description: string | null;
}

export interface Session {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  device_label: string | null;
  is_active: boolean;
  last_active_at: string;
  expires_at: string;
  created_at: string;
  is_current: boolean;
}

export interface MessageResponse {
  message: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
