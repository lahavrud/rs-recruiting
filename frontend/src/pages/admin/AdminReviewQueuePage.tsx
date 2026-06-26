import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import PageHeader from "@/components/ui/PageHeader";
import { usePageTitle } from "@/hooks/usePageTitle";
import { getAdminOverview, type AdminInboxCounts } from "@/services/adminOverview";

import ApplicationsQueue from "./components/ApplicationsQueue";
import CompaniesQueue from "./components/CompaniesQueue";
import JobsQueue from "./components/JobsQueue";

type QueueTab = "applications" | "jobs" | "companies";

const TABS: {
  tab: QueueTab;
  labelKey: string;
  badgeField: keyof AdminInboxCounts;
}[] = [
  {
    tab: "applications",
    labelKey: "admin:reviewQueue.tabs.applications",
    badgeField: "new_applications",
  },
  {
    tab: "jobs",
    labelKey: "admin:reviewQueue.tabs.jobs",
    badgeField: "pending_jobs",
  },
  {
    tab: "companies",
    labelKey: "admin:reviewQueue.tabs.companies",
    badgeField: "pending_companies",
  },
];

export default function AdminReviewQueuePage() {
  const { t } = useTranslation(["admin", "common"]);
  usePageTitle(t("admin:reviewQueue.title"));

  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab") as QueueTab | null;
  const tab: QueueTab =
    rawTab === "jobs" || rawTab === "companies" ? rawTab : "applications";

  const [counts, setCounts] = useState<AdminInboxCounts | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then((data) => setCounts(data.inbox))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  function setTab(next: QueueTab) {
    setParams(next === "applications" ? {} : { tab: next }, { replace: true });
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <h1 data-page-heading className="sr-only">
        {t("admin:reviewQueue.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin:reviewQueue.title")}
        subtitle={t("admin:reviewQueue.subtitle")}
      />

      {/* Tab bar */}
      <div className="mb-4 flex gap-0.5 border-b border-white/8">
        {TABS.map(({ tab: t_, labelKey, badgeField }) => {
          const count = counts?.[badgeField] ?? null;
          const isActive = tab === t_;
          return (
            <button
              key={t_}
              type="button"
              onClick={() => setTab(t_)}
              className={`flex items-center gap-2 border-b-2 px-4 pb-2.5 pt-1 text-sm font-medium transition ${
                isActive
                  ? "border-copper text-white"
                  : "border-transparent text-white/45 hover:text-white/70"
              }`}
            >
              {t(labelKey)}
              {count != null && count > 0 && (
                <span className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-copper/20 px-1 py-px text-[10px] font-semibold text-copper">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Queue content — flex-1 min-h-0 so SplitPaneLayout inside can fill */}
      <div className="flex min-h-0 flex-1">
        {tab === "applications" && <ApplicationsQueue />}
        {tab === "jobs" && <JobsQueue />}
        {tab === "companies" && <CompaniesQueue />}
      </div>
    </div>
  );
}
