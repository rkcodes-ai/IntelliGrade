import { apiClient } from "@/api/client";
import type {
  ChangePasswordRequest,
  ForgotPasswordRequest,
  LoginRequest,
  MessageResponse,
  ResetPasswordRequest,
  TokenResponse,
} from "@/types/auth";

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
  return data;
}

export async function logout(): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>("/auth/logout");
  return data;
}

export async function forgotPassword(payload: ForgotPasswordRequest): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>("/auth/forgot-password", payload);
  return data;
}

export async function resetPassword(payload: ResetPasswordRequest): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>("/auth/reset-password", payload);
  return data;
}

export async function changePassword(payload: ChangePasswordRequest): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>("/auth/change-password", payload);
  return data;
}
