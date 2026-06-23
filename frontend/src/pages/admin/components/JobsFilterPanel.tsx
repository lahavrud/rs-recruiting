import type { Dispatch, SetStateAction } from "react";

import { useTranslation } from "react-i18next";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import FunnelIcon from "@/components/admin/FunnelIcon";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";
import Eyebrow from "@/components/ui/Eyebrow";
import FilterPill from "@/components/ui/FilterPill";
import RangeSlider from "@/components/ui/RangeSlider";
import SearchInput from "@/components/ui/SearchInput";

const ALL_FILTER = "ALL";

export interface SalaryBounds {
  min: number;
  max: number;
}

export interface SearchState {
  query: string;
  setQuery: Dispatch<SetStateAction<string>>;
}

export interface FilterState {
  filter: string;
  setFilter: Dispatch<SetStateAction<string>>;
  filterTabs: string[];
  statusLabels: Record<string, string>;
  uniqueLocations: string[];
  selectedLocations: string[];
  setSelectedLocations: Dispatch<SetStateAction<string[]>>;
  isFeaturedOnly: boolean;
  setIsFeaturedOnly: Dispatch<SetStateAction<boolean>>;
}

export interface SalaryFilterState {
  salaryBounds: SalaryBounds;
  effectiveSalaryRange: [number, number];
  isSalaryActive: boolean;
  setSalaryRange: Dispatch<SetStateAction<[number, number] | null>>;
}

export interface CompanyFilterState {
  uniqueCompanies: number[];
  companyFilter: number[];
  setCompanyFilter: Dispatch<SetStateAction<number[]>>;
  companyNameById: Map<number, string>;
}

export interface UIState {
  activeFilterCount: number;
  isFilterOpen: boolean;
  setIsFilterOpen: Dispatch<SetStateAction<boolean>>;
  clearFilters: () => void;
}

export interface JobsFilterPanelProps {
  search: SearchState;
  filters: FilterState;
  salary: SalaryFilterState;
  company: CompanyFilterState;
  ui: UIState;
}

export default function JobsFilterPanel({
  search,
  filters,
  salary,
  company,
  ui,
}: JobsFilterPanelProps) {
  const { query, setQuery } = search;
  const {
    filter,
    setFilter,
    filterTabs,
    statusLabels,
    uniqueLocations,
    selectedLocations,
    setSelectedLocations,
    isFeaturedOnly,
    setIsFeaturedOnly,
  } = filters;
  const { salaryBounds, effectiveSalaryRange, isSalaryActive, setSalaryRange } =
    salary;
  const { uniqueCompanies, companyFilter, setCompanyFilter, companyNameById } =
    company;
  const { activeFilterCount, isFilterOpen, setIsFilterOpen } = ui;
  const { t } = useTranslation(['admin', 'common', 'publicJobs']);

  return (
    <>
      {/* Search + filter toggle */}
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin:jobs.searchPlaceholder")}
            isClearable
          />
        </div>
        <button
          type="button"
          onClick={() => setIsFilterOpen((o) => !o)}
          aria-expanded={isFilterOpen}
          aria-label={t("admin:jobs.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            isFilterOpen
              ? "border-copper/50 bg-copper/10 text-white"
              : "border-white/15 bg-card-raised/40 text-white/75 hover:border-copper/40 hover:text-white"
          }`}
        >
          <FunnelIcon />
          <span className="hidden sm:inline">{t("admin:jobs.filters")}</span>
          {activeFilterCount > 0 && (
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {/* Active filter chips */}
      {activeFilterCount > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {filter !== ALL_FILTER && (
            <ActiveFilterChip
              label={`${t("admin:jobs.fields.status")}: ${statusLabels[filter]}`}
              onRemove={() => setFilter(ALL_FILTER)}
            />
          )}
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common:search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {selectedLocations.map((loc) => (
            <ActiveFilterChip
              key={`loc-${loc}`}
              label={`${t("publicJobs:board.locationLabel")}: ${loc}`}
              onRemove={() =>
                setSelectedLocations((prev) => prev.filter((x) => x !== loc))
              }
            />
          ))}
          {isSalaryActive && (
            <ActiveFilterChip
              label={`${t("publicJobs:board.salaryRange")}: ${effectiveSalaryRange[0].toLocaleString("he-IL")}–${effectiveSalaryRange[1].toLocaleString("he-IL")} ₪`}
              onRemove={() => setSalaryRange(null)}
            />
          )}
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin:jobs.fields.company")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() =>
                setCompanyFilter((prev) => prev.filter((x) => x !== id))
              }
            />
          ))}
          {isFeaturedOnly && (
            <ActiveFilterChip
              label={t("admin:jobs.featuredOnly")}
              onRemove={() => setIsFeaturedOnly(false)}
            />
          )}
        </div>
      )}

      {/* Animated filter panel — grid-rows 0fr→1fr */}
      <div
        className={`mb-4 grid transition-[grid-template-rows] duration-300 ease-out ${
          isFilterOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`space-y-4 rounded-md border border-white/8 bg-card/40 p-4 transition-opacity duration-200 ${
              isFilterOpen ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            <div>
              <Eyebrow size="md" className="mb-2">
                {t("admin:jobs.fields.status")}
              </Eyebrow>
              <div className="flex flex-wrap gap-1.5">
                {filterTabs.map((tab) => (
                  <FilterPill
                    key={tab}
                    isActive={filter === tab}
                    onClick={() => setFilter(tab)}
                  >
                    {tab === ALL_FILTER
                      ? t("admin:jobs.filterAll")
                      : statusLabels[tab]}
                  </FilterPill>
                ))}
              </div>
            </div>
            {uniqueLocations.length >= 2 && (
              <div>
                <Eyebrow size="md" className="mb-2">
                  {t("publicJobs:board.locationLabel")}
                </Eyebrow>
                <div className="flex flex-wrap gap-1.5">
                  <FilterPill
                    compact
                    isActive={selectedLocations.length === 0}
                    onClick={() => setSelectedLocations([])}
                  >
                    {t("publicJobs:board.allLocations")}
                  </FilterPill>
                  {uniqueLocations.map((loc) => {
                    const isActive = selectedLocations.includes(loc);
                    return (
                      <FilterPill
                        key={loc}
                        compact
                        isActive={isActive}
                        onClick={() =>
                          setSelectedLocations((prev) =>
                            isActive
                              ? prev.filter((x) => x !== loc)
                              : [...prev, loc],
                          )
                        }
                      >
                        {loc}
                      </FilterPill>
                    );
                  })}
                </div>
              </div>
            )}
            <div>
              <div className="mb-2 flex items-center justify-between gap-3">
                <Eyebrow size="md">{t("publicJobs:board.salaryRange")}</Eyebrow>
                {isSalaryActive && (
                  <button
                    type="button"
                    onClick={() =>
                      setSalaryRange([salaryBounds.min, salaryBounds.max])
                    }
                    className="text-[11px] text-copper/70 transition hover:text-copper"
                  >
                    {t("publicJobs:board.resetSalary")}
                  </button>
                )}
              </div>
              <RangeSlider
                min={salaryBounds.min}
                max={salaryBounds.max}
                step={500}
                value={effectiveSalaryRange}
                onChange={(next) => setSalaryRange(next)}
                formatValue={(n) => `${n.toLocaleString("he-IL")} ₪`}
                ariaLabelMin={t("publicJobs:board.salaryMinAria")}
                ariaLabelMax={t("publicJobs:board.salaryMaxAria")}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Eyebrow size="md" className="mb-1.5">
                  {t("admin:jobs.fields.company")}
                </Eyebrow>
                <SearchableMultiSelect<number>
                  values={companyFilter}
                  onChange={setCompanyFilter}
                  options={uniqueCompanies.map((id) => ({
                    value: id,
                    label: companyNameById.get(id) ?? `#${id}`,
                  }))}
                  placeholder={t("admin:jobs.companyAll")}
                />
              </div>
              <label className="mt-auto inline-flex items-center gap-2 text-sm text-white/80">
                <input
                  type="checkbox"
                  checked={isFeaturedOnly}
                  onChange={(e) => setIsFeaturedOnly(e.target.checked)}
                  className="size-4 rounded border-white/20 bg-well text-copper focus:ring-copper"
                />
                {t("admin:jobs.featuredOnly")}
              </label>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
