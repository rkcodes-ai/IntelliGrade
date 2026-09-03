import { Building2 } from "lucide-react";

import { Select } from "@/components/ui/select";
import { useMyInstitutions } from "@/hooks/useMyInstitutions";
import { useAppDispatch, useAppSelector } from "@/store";
import { setCurrentInstitution } from "@/store/slices/institutionSlice";

/** Topbar tenant switcher — every Academic Domain page depends on this selection. */
export function InstitutionSwitcher() {
  const dispatch = useAppDispatch();
  const currentInstitutionId = useAppSelector((state) => state.institution.currentInstitutionId);
  const { data: institutions, isLoading } = useMyInstitutions();

  if (isLoading || !institutions || institutions.length === 0) {
    return null;
  }

  if (institutions.length === 1) {
    return (
      <span className="hidden items-center gap-2 text-sm text-muted-foreground md:flex">
        <Building2 className="h-4 w-4" />
        {institutions[0].name}
      </span>
    );
  }

  return (
    <div className="hidden items-center gap-2 md:flex">
      <Building2 className="h-4 w-4 text-muted-foreground" />
      <Select
        aria-label="Current institution"
        value={currentInstitutionId ?? ""}
        onChange={(event) => dispatch(setCurrentInstitution(event.target.value))}
        className="h-9 w-auto"
      >
        {institutions.map((institution) => (
          <option key={institution.id} value={institution.id}>
            {institution.name}
          </option>
        ))}
      </Select>
    </div>
  );
}
