import { useTranslation } from "react-i18next";

import RangeSlider from "@/components/ui/RangeSlider";
import SearchInput from "@/components/ui/SearchInput";

import { SALARY_STEP, formatSalaryShort } from "./jobBoardUtils";

import type { SalaryBounds } from "./jobBoardUtils";

export type { SalaryBounds };

export interface FilterPanelProps {
  /** When true, render a search input at the top of the panel. */
  shouldShowSearch?: boolean;
  query: string;
  onQueryChange: (q: string) => void;
  locations: string[];
  selectedLocations: string[];
  onLocationsChange: (next: string[]) => void;
  salaryBounds: SalaryBounds;
  salaryRange: [number, number];
  onSalaryChange: (range: [number, number]) => void;
  isSalaryActive: boolean;
  onResetSalary: () => void;
  hasActiveFilter: boolean;
  onClearAll: () => void;
}

export default function JobBoardFilterPanel({
  shouldShowSearch = false,
  query,
  onQueryChange,
  locations,
  selectedLocations,
  onLocationsChange,
  salaryBounds,
  salaryRange,
  onSalaryChange,
  isSalaryActive,
  onResetSalary,
  hasActiveFilter,
  onClearAll,
}: FilterPanelProps) {
  const { t } = useTranslation(['common', 'publicJobs']);

  return (
    <div className="space-y-6">
      {shouldShowSearch && (
        <div>
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
            {t("common:search")}
          </p>
          <SearchInput
            value={query}
            onChange={onQueryChange}
            placeholder={t("publicJobs:board.searchPlaceholder")}
            isShortcutDisabled
            isClearable
          />
        </div>
      )}

      {locations.length >= 2 && (
        <div>
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
            {t("publicJobs:board.locationLabel")}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onLocationsChange([])}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition",
                selectedLocations.length === 0
                  ? "bg-copper text-white"
                  : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85",
              ].join(" ")}
            >
              {t("publicJobs:board.allLocations")}
            </button>
            {locations.map((loc) => {
              const active = selectedLocations.includes(loc);
              return (
                <button
                  key={loc}
                  type="button"
                  onClick={() =>
                    onLocationsChange(
                      active
                        ? selectedLocations.filter((x) => x !== loc)
                        : [...selectedLocations, loc],
                    )
                  }
                  className={[
                    "rounded-full px-3 py-1.5 text-xs font-medium transition",
                    active
                      ? "bg-copper text-white"
                      : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85",
                  ].join(" ")}
                >
                  {loc}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-copper">
            {t("publicJobs:board.salaryRange")}
          </p>
          {isSalaryActive && (
            <button
              type="button"
              onClick={onResetSalary}
              className="text-[11px] text-copper/70 transition hover:text-copper"
            >
              {t("publicJobs:board.resetSalary")}
            </button>
          )}
        </div>
        <RangeSlider
          min={salaryBounds.min}
          max={salaryBounds.max}
          step={SALARY_STEP}
          value={salaryRange}
          onChange={onSalaryChange}
          formatValue={formatSalaryShort}
          ariaLabelMin={t("publicJobs:board.salaryMinAria")}
          ariaLabelMax={t("publicJobs:board.salaryMaxAria")}
        />
      </div>

      {hasActiveFilter && (
        <button
          type="button"
          onClick={onClearAll}
          className="w-full rounded-sm border border-white/15 px-3 py-2 text-xs font-medium text-white/65 transition hover:border-copper/50 hover:text-copper"
        >
          {t("publicJobs:board.clearFilters")}
        </button>
      )}
    </div>
  );
}
