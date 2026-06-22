import type { Dispatch, SetStateAction } from "react";

import { useTranslation } from "react-i18next";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";
import Eyebrow from "@/components/ui/Eyebrow";
import FilterPill from "@/components/ui/FilterPill";
import { ApplicationStatus } from "@/types/api";

const ALL_FILTER = "ALL";
type FilterValue = string;

const ALL_STATUSES = [
  ApplicationStatus.NEW,
  ApplicationStatus.APPROVED_BY_ADMIN,
  ApplicationStatus.REJECTED,
  ApplicationStatus.HIRED,
  ApplicationStatus.WITHDRAWN,
];

export interface FilterState {
  filter: FilterValue;
  setFilter: Dispatch<SetStateAction<FilterValue>>;
  query: string;
  setQuery: Dispatch<SetStateAction<string>>;
  jobFilter: number[];
  setJobFilter: Dispatch<SetStateAction<number[]>>;
  filterCandidateId: number | undefined;
  setFilterCandidateId: Dispatch<SetStateAction<number | undefined>>;
  companyFilter: number[];
  setCompanyFilter: Dispatch<SetStateAction<number[]>>;
}

export interface LookupMaps {
  allJobs: { id: number; title: string; company_id: number }[];
  companyNameById: Map<number, string>;
  jobTitleById: Map<number, string>;
}

export interface UIState {
  activeFilterCount: number;
  filterOpen: boolean;
  statusLabels: Record<string, string>;
}

export interface ApplicationsFilterPanelProps {
  filterState: FilterState;
  lookupMaps: LookupMaps;
  uiState: UIState;
}

export default function ApplicationsFilterPanel({
  filterState,
  lookupMaps,
  uiState,
}: ApplicationsFilterPanelProps) {
  const {
    filter,
    setFilter,
    query,
    setQuery,
    jobFilter,
    setJobFilter,
    filterCandidateId,
    setFilterCandidateId,
    companyFilter,
    setCompanyFilter,
  } = filterState;
  const { allJobs, companyNameById, jobTitleById } = lookupMaps;
  const { activeFilterCount, filterOpen, statusLabels } = uiState;
  const { t } = useTranslation(['admin', 'common']);
  const filterTabs: FilterValue[] = [ALL_FILTER, ...ALL_STATUSES];

  return (
    <>
      {/* Active filter chips */}
      {activeFilterCount > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {filter !== ALL_FILTER && (
            <ActiveFilterChip
              label={`${t("admin:applications.table.status")}: ${statusLabels[filter]}`}
              onRemove={() => setFilter(ALL_FILTER)}
            />
          )}
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common:search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {jobFilter.map((id) => (
            <ActiveFilterChip
              key={`job-${id}`}
              label={`${t("common:filteredByJob")}: ${jobTitleById.get(id) ?? `#${id}`}`}
              onRemove={() => setJobFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
          {filterCandidateId != null && (
            <ActiveFilterChip
              label={`${t("common:filteredByCandidate")} #${filterCandidateId}`}
              onRemove={() => setFilterCandidateId(undefined)}
            />
          )}
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin:applications.filterByCompany")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() => setCompanyFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
        </div>
      )}

      {/* Filter panel — animated open/close */}
      <div
        className={`mb-4 grid transition-[grid-template-rows] duration-300 ease-out ${
          filterOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`space-y-4 rounded-md border border-white/8 bg-card/40 p-4 transition-opacity duration-200 ${
              filterOpen ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            <div>
              <Eyebrow size="md" className="mb-2">
                {t("admin:applications.table.status")}
              </Eyebrow>
              <div className="flex flex-wrap gap-1.5">
                {filterTabs.map((tab) => (
                  <FilterPill
                    key={tab}
                    active={filter === tab}
                    onClick={() => setFilter(tab)}
                  >
                    {tab === ALL_FILTER
                      ? t("admin:applications.filterAll")
                      : statusLabels[tab]}
                  </FilterPill>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* Company first → in RTL it lands on the visual right */}
              <div>
                <Eyebrow size="md" className="mb-1.5">
                  {t("admin:applications.filterByCompany")}
                </Eyebrow>
                <SearchableMultiSelect<number>
                  values={companyFilter}
                  onChange={(next) => {
                    setCompanyFilter(next);
                    // Drop any selected jobs that no longer match an active company.
                    if (next.length > 0 && jobFilter.length > 0) {
                      const allowed = new Set(
                        allJobs
                          .filter((j) => next.includes(j.company_id))
                          .map((j) => j.id),
                      );
                      setJobFilter((prev) => prev.filter((id) => allowed.has(id)));
                    }
                  }}
                  options={Array.from(companyNameById.entries()).map(([id, name]) => ({
                    value: id,
                    label: name,
                  }))}
                  placeholder={t("admin:applications.allCompanies")}
                />
              </div>
              <div>
                <Eyebrow size="md" className="mb-1.5">
                  {t("admin:applications.filterByJob")}
                </Eyebrow>
                <SearchableMultiSelect<number>
                  values={jobFilter}
                  onChange={setJobFilter}
                  options={allJobs
                    .filter(
                      (j) =>
                        companyFilter.length === 0 ||
                        companyFilter.includes(j.company_id),
                    )
                    .map((j) => ({ value: j.id, label: j.title }))}
                  placeholder={t("admin:applications.allJobs")}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
