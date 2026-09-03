import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { listMyInstitutions } from "@/api/institutions";
import { useAppDispatch, useAppSelector } from "@/store";
import { setCurrentInstitution } from "@/store/slices/institutionSlice";

/**
 * Fetches the institutions the current user may act within and, if none is
 * yet selected (or the previously-selected one is no longer in the list —
 * e.g. membership revoked), auto-selects the first one. Powers
 * `InstitutionSwitcher` and should be mounted once near the app root
 * (`DashboardLayout`) so the selection is ready before any tenant-scoped
 * page renders.
 */
export function useMyInstitutions() {
  const dispatch = useAppDispatch();
  const currentInstitutionId = useAppSelector((state) => state.institution.currentInstitutionId);

  const query = useQuery({
    queryKey: ["institutions", "mine"],
    queryFn: listMyInstitutions,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!query.data || query.data.length === 0) return;
    const stillValid = query.data.some((institution) => institution.id === currentInstitutionId);
    if (!stillValid) {
      dispatch(setCurrentInstitution(query.data[0].id));
    }
  }, [query.data, currentInstitutionId, dispatch]);

  return query;
}
