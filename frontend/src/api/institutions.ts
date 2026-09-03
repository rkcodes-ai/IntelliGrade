import { apiClient } from "@/api/client";
import { createCrudApi } from "@/api/createCrudApi";
import type { Institution, InstitutionCreate, InstitutionUpdate, UserInstitution } from "@/types/academic";

export const institutionsApi = createCrudApi<Institution, InstitutionCreate, InstitutionUpdate>(
  "/institutions",
);

/** Institutions the current user may select as their active tenant. */
export async function listMyInstitutions(): Promise<Institution[]> {
  const { data } = await apiClient.get<Institution[]>("/institutions/mine");
  return data;
}

export async function listInstitutionMembers(institutionId: string): Promise<UserInstitution[]> {
  const { data } = await apiClient.get<UserInstitution[]>(`/institutions/${institutionId}/members`);
  return data;
}

export async function assignInstitutionMember(
  institutionId: string,
  payload: { user_id: string; is_primary?: boolean },
): Promise<UserInstitution> {
  const { data } = await apiClient.post<UserInstitution>(
    `/institutions/${institutionId}/members`,
    payload,
  );
  return data;
}

export async function revokeInstitutionMember(institutionId: string, userId: string): Promise<void> {
  await apiClient.delete(`/institutions/${institutionId}/members/${userId}`);
}
