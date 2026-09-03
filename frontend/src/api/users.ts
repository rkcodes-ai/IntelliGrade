import { apiClient } from "@/api/client";
import type { User, UserProfileUpdate } from "@/types/auth";

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/users/me");
  return data;
}

export async function updateMe(payload: UserProfileUpdate): Promise<User> {
  const { data } = await apiClient.patch<User>("/users/me", payload);
  return data;
}

export async function listUsers(params?: { limit?: number; offset?: number }): Promise<User[]> {
  const { data } = await apiClient.get<User[]>("/users", { params });
  return data;
}

export async function getUser(userId: string): Promise<User> {
  const { data } = await apiClient.get<User>(`/users/${userId}`);
  return data;
}

export async function deactivateUser(userId: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/deactivate`);
  return data;
}

export async function activateUser(userId: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/activate`);
  return data;
}

export async function deleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${userId}`);
}
