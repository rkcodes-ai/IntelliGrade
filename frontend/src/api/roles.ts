import { apiClient } from "@/api/client";
import type { Role } from "@/types/auth";

export async function getRoles(): Promise<Role[]> {
  const { data } = await apiClient.get<Role[]>("/roles");
  return data;
}
