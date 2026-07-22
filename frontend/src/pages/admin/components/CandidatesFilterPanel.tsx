import type { Dispatch, SetStateAction } from "react";

import { useTranslation } from "react-i18next";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import FilterPanelShell from "@/components/admin/FilterPanelShell";
import CheckboxField from "@/components/ui/CheckboxField";
import Eyebrow from "@/components/ui/Eyebrow";

export interface CandidatesFilterPanelProps {
  isFilterOpen: boolean;
  activeFilterCount: number;
  query: string;
  setQuery: Dispatch<SetStateAction<string>>;
  includeDeleted: boolean;
  setIncludeDeleted: Dispatch<SetStateAction<boolean>>;
}

/** Filter panel for the admin candidates list — mirrors the jobs/applications panels. */
export default function CandidatesFilterPanel({
  isFilterOpen,
  activeFilterCount,
  query,
  setQuery,
  includeDeleted,
  setIncludeDeleted,
}: CandidatesFilterPanelProps) {
  const { t } = useTranslation(["admin", "common"]);

  return (
    <>
      {activeFilterCount > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common:search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {includeDeleted && (
            <ActiveFilterChip
              label={t("admin:candidates.showDeletedToggle")}
              onRemove={() => setIncludeDeleted(false)}
            />
          )}
        </div>
      )}

      <FilterPanelShell isOpen={isFilterOpen}>
        <div>
          <Eyebrow size="md" className="mb-2">
            {t("admin:candidates.title")}
          </Eyebrow>
          <CheckboxField
            checked={includeDeleted}
            onChange={setIncludeDeleted}
            label={t("admin:candidates.showDeletedToggle")}
          />
          <p className="mt-1.5 text-[11px] text-white/35">
            {t("admin:candidates.showDeletedHint")}
          </p>
        </div>
      </FilterPanelShell>
    </>
  );
}
