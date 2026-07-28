import type { Dispatch, SetStateAction } from "react";

import { useTranslation } from "react-i18next";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import FilterPanelShell from "@/components/admin/FilterPanelShell";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";
import CheckboxField from "@/components/ui/CheckboxField";
import Eyebrow from "@/components/ui/Eyebrow";
import FilterPill from "@/components/ui/FilterPill";
import { ApplicationStatus } from "@/types/enums";
const ALL_FILTER = "ALL";
type FilterValue = string;

const ALL_STATUSES = [
  ApplicationStatus.PENDING_ADMIN_REVIEW,
  ApplicationStatus.APPROVED_BY_ADMIN,
  ApplicationStatus.INTERVIEWING,
  ApplicationStatus.OFFER,
  ApplicationStatus.HIRED,
  ApplicationStatus.REJECTED_BY_COMPANY,
  ApplicationStatus.REJECTED_BY_ADMIN,
  ApplicationStatus.WITHDRAWN,
];

export interface FilterState {
  filter: FilterValue;
  setFilter: Dispatch<SetStateAction<FilterValue>>;
  query: string;
  setQuery: Dispatch<SetStateAction<string>>;
  jobFilter: number[];
  setJobFilter: Dispatch<SetStateAction<number[]>>;
  companyFilter: number[];
  setCompanyFilter: Dispatch<SetStateAction<number[]>>;
  includeDeleted: boolean;
  setIncludeDeleted: Dispatch<SetStateAction<boolean>>;
}

export interface LookupMaps {
  allJobs: { id: number; title: string; company_id: number }[];
  companyNameById: Map<number, string>;
  jobTitleById: Map<number, string>;
}

export interface UIState {
  activeFilterCount: number;
  isFilterOpen: boolean;
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
    companyFilter,
    setCompanyFilter,
    includeDeleted,
    setIncludeDeleted,
  } = filterState;
  const { allJobs, companyNameById, jobTitleById } = lookupMaps;
  const { activeFilterCount, isFilterOpen, statusLabels } = uiState;
  const { t } = useTranslation(["admin", "common"]);
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
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin:applications.filterByCompany")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() => setCompanyFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
          {includeDeleted && (
            <ActiveFilterChip
              label={t("admin:candidates.showDeletedToggle")}
              onRemove={() => setIncludeDeleted(false)}
            />
          )}
        </div>
      )}

      {/* Filter panel — animated open/close */}
      <FilterPanelShell isOpen={isFilterOpen}>
        <div>
          <Eyebrow size="md" className="mb-2">
            {t("admin:applications.table.status")}
          </Eyebrow>
          <div className="flex flex-wrap gap-1.5">
            {filterTabs.map((tab) => (
              <FilterPill
                key={tab}
                isActive={filter === tab}
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
                    allJobs.filter((j) => next.includes(j.company_id)).map((j) => j.id),
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
                    companyFilter.length === 0 || companyFilter.includes(j.company_id),
                )
                .map((j) => ({ value: j.id, label: j.title }))}
              placeholder={t("admin:applications.allJobs")}
            />
          </div>
        </div>
        <CheckboxField
          checked={includeDeleted}
          onChange={setIncludeDeleted}
          label={t("admin:candidates.showDeletedToggle")}
        />
      </FilterPanelShell>
    </>
  );
}
