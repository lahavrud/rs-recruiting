import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import { getJobApplications } from "@/services/companyJobs";
import type { CompanyApplicationRead } from "@/types/companies";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

const KANBAN_COLUMNS: { status: string; labelKey: string }[] = [
  { status: ApplicationStatus.NEW, labelKey: "company:jobs.kanban.columns.NEW" },
  {
    status: ApplicationStatus.APPROVED_BY_ADMIN,
    labelKey: "company:jobs.kanban.columns.APPROVED_BY_ADMIN",
  },
  { status: ApplicationStatus.HIRED, labelKey: "company:jobs.kanban.columns.HIRED" },
  { status: ApplicationStatus.REJECTED, labelKey: "company:jobs.kanban.columns.REJECTED" },
  { status: ApplicationStatus.WITHDRAWN, labelKey: "company:jobs.kanban.columns.WITHDRAWN" },
];

const COLUMN_ACCENT: Record<string, string> = {
  [ApplicationStatus.NEW]: "border-info/30 text-info",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "border-copper/30 text-copper",
  [ApplicationStatus.HIRED]: "border-hired/30 text-hired",
  [ApplicationStatus.REJECTED]: "border-danger/30 text-danger",
  [ApplicationStatus.WITHDRAWN]: "border-white/12 text-white/35",
};

const COLUMN_HEADER_BG: Record<string, string> = {
  [ApplicationStatus.NEW]: "bg-info/8",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "bg-copper/8",
  [ApplicationStatus.HIRED]: "bg-hired/8",
  [ApplicationStatus.REJECTED]: "bg-danger/8",
  [ApplicationStatus.WITHDRAWN]: "bg-white/4",
};

function CandidateCard({ app }: { app: CompanyApplicationRead }) {
  const { t } = useTranslation("company");
  return (
    <div className="rounded-lg border border-white/8 bg-card-raised p-3 space-y-1.5">
      <p className="text-sm font-medium text-white/85">{app.candidate.full_name}</p>
      <p className="text-xs text-white/40">{app.candidate.email}</p>
      {app.candidate.phone ? (
        <p className="text-xs text-white/35" dir="ltr">
          {app.candidate.phone}
        </p>
      ) : (
        <p className="text-xs text-white/20">{t("company:jobs.kanban.noPhone")}</p>
      )}
      <p className="text-[10px] text-white/25">
        {t("company:jobs.kanban.appliedOn")}
        {formatDate(app.created_at)}
      </p>
    </div>
  );
}

interface JobKanbanProps {
  jobId: number;
}

export default function JobKanban({ jobId }: JobKanbanProps) {
  const { t } = useTranslation("company");
  const [applications, setApplications] = useState<CompanyApplicationRead[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getJobApplications(jobId)
      .then((apps) => {
        if (!cancelled) setApplications(apps);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (error) {
    return (
      <p className="py-8 text-center text-sm text-danger">
        {t("company:jobs.kanban.loadError")}
      </p>
    );
  }

  if (applications === null) {
    return (
      <p className="py-8 text-center text-sm text-white/30">
        {t("company:jobs.kanban.loading")}
      </p>
    );
  }

  if (applications.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-white/30">
        {t("company:jobs.kanban.empty")}
      </p>
    );
  }

  const byStatus = Object.fromEntries(
    KANBAN_COLUMNS.map(({ status }) => [
      status,
      applications.filter((a) => a.status === status),
    ]),
  );

  const activeColumns = KANBAN_COLUMNS.filter(({ status }) => byStatus[status].length > 0);

  return (
    <div className="overflow-x-auto">
      <div
        className="flex gap-3 pb-2"
        style={{ minWidth: `${activeColumns.length * 200}px` }}
      >
        {activeColumns.map(({ status, labelKey }) => {
          const cards = byStatus[status];
          const accentCls = COLUMN_ACCENT[status] ?? "border-white/12 text-white/35";
          const headerBg = COLUMN_HEADER_BG[status] ?? "bg-white/4";
          return (
            <div key={status} className="flex w-48 shrink-0 flex-col gap-2">
              <div
                className={`flex items-center justify-between rounded-lg border px-3 py-2 ${accentCls} ${headerBg}`}
              >
                <span className="text-[10px] font-semibold uppercase tracking-widest">
                  {t(labelKey)}
                </span>
                <span className="rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold">
                  {cards.length}
                </span>
              </div>
              <div className="space-y-2">
                {cards.map((app) => (
                  <CandidateCard key={app.id} app={app} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
