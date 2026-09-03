import { apiClient } from "@/api/client";
import type { Permission } from "@/types/auth";

export async function getPermissions(): Promise<Permission[]> {
  const { data } = await apiClient.get<Permission[]>("/permissions");
  return data;
}
