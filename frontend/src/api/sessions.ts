import { apiClient } from "@/api/client";
import type { Session } from "@/types/auth";

export async function getSessions(): Promise<Session[]> {
  const { data } = await apiClient.get<Session[]>("/sessions");
  return data;
}

export async function revokeSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/sessions/${sessionId}`);
}
