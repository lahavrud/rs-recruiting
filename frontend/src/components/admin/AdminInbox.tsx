import { useEffect, useState, type ReactNode } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getAdminOverview, type AdminInboxCounts } from "@/services/adminOverview";

interface ItemConfig {
  key: string;
  label: string;
  hint: string;
  empty: string;
  to: string;
  icon: ReactNode;
  n: number | null;
  ageDays: number | null;
}

export default function AdminInbox() {
  const { t } = useTranslation("dashboard");
  const [counts, setCounts] = useState<AdminInboxCounts | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then((data) => setCounts(data.inbox))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  const items: ItemConfig[] = [
    {
      key: "invites",
      label: t("dashboard:inbox.invites.label"),
      hint: t("dashboard:inbox.invites.hint"),
      empty: t("dashboard:inbox.invites.empty"),
      to: "/admin/companies?view=invites",
      icon: <EnvelopeIcon />,
      n: counts?.pending_invites ?? null,
      ageDays: null,
    },
    {
      key: "companies",
      label: t("dashboard:inbox.companies.label"),
      hint: t("dashboard:inbox.companies.hint"),
      empty: t("dashboard:inbox.companies.empty"),
      to: "/admin/companies?view=pending",
      icon: <UserCheckIcon />,
      n: counts?.pending_companies ?? null,
      ageDays: counts?.oldest_pending_company_days ?? null,
    },
    {
      key: "jobs",
      label: t("dashboard:inbox.jobs.label"),
      hint: t("dashboard:inbox.jobs.hint"),
      empty: t("dashboard:inbox.jobs.empty"),
      to: "/admin/jobs?status=PENDING_APPROVAL",
      icon: <BriefcaseIcon />,
      n: counts?.pending_jobs ?? null,
      ageDays: counts?.oldest_pending_job_days ?? null,
    },
    {
      key: "applications",
      label: t("dashboard:inbox.applications.label"),
      hint: t("dashboard:inbox.applications.hint"),
      empty: t("dashboard:inbox.applications.empty"),
      to: "/admin/applications?status=NEW",
      icon: <DocumentIcon />,
      n: counts?.new_applications ?? null,
      ageDays: counts?.oldest_new_application_days ?? null,
    },
  ];

  const allClear = items.every((it) => it.n != null && it.n === 0);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          {t("dashboard:inbox.title")}
        </p>
        <div className="flex items-center gap-4">
          {allClear && (
            <p className="text-xs text-white/40">{t("dashboard:inbox.allClear")}</p>
          )}
          <Link
            to="/admin/companies?view=invites&action=invite"
            className="text-xs font-medium text-copper/75 transition hover:text-copper"
          >
            {t("dashboard:inbox.newInvite")}
          </Link>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item) => (
          <InboxCard key={item.key} item={item} />
        ))}
      </div>
    </div>
  );
}

function urgencyLabel(t: ReturnType<typeof useTranslation<"dashboard">>["t"], days: number): string {
  if (days === 0) return t("dashboard:inbox.urgency.today");
  return t("dashboard:inbox.urgency.days", { count: days });
}

function InboxCard({ item }: { item: ItemConfig }) {
  const { t } = useTranslation("dashboard");
  const isLoading = item.n == null;
  const isEmpty = !isLoading && item.n === 0;
  const isUrgent = !isEmpty && item.ageDays != null && item.ageDays >= 3;
  const display = isLoading ? "—" : item.n;

  return (
    <Link
      to={item.to}
      className={`group relative block overflow-hidden rounded-xl border p-4 transition duration-200 ${
        isEmpty
          ? "border-white/8 bg-card hover:border-white/15"
          : isUrgent
            ? "border-warning/30 bg-card hover:border-warning/50 hover:bg-card-raised"
            : "border-copper/25 bg-card hover:border-copper/45 hover:bg-card-raised"
      }`}
    >
      {/* Urgency accent stripe */}
      {isUrgent && (
        <div className="absolute inset-x-0 top-0 h-0.5 bg-warning/60" />
      )}

      {/* Top row: icon + chevron only — keeps the row from overflowing on narrow cards */}
      <div className="flex items-center justify-between">
        <span
          className={`inline-flex size-8 items-center justify-center rounded-full ${
            isEmpty
              ? "bg-white/5 text-white/35"
              : isUrgent
                ? "bg-warning/15 text-warning"
                : "bg-copper/15 text-copper"
          }`}
        >
          {item.icon}
        </span>
        <span
          aria-hidden="true"
          className={`size-4 transition group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5 ${
            isEmpty ? "text-white/20" : isUrgent ? "text-warning/50" : "text-copper/60"
          }`}
        >
          <ChevronIcon />
        </span>
      </div>

      <p
        className={`mt-3 text-3xl font-semibold leading-none ${
          isLoading ? "text-white/25" : isEmpty ? "text-white/45" : "text-white/95"
        }`}
      >
        {display}
      </p>
      <p className="mt-2 text-sm font-medium text-white/80">{item.label}</p>
      <p className="mt-1 text-xs text-white/40">{isEmpty ? item.empty : item.hint}</p>
      {/* Urgency age on its own line — avoids cramming into the header row */}
      {!isEmpty && !isLoading && item.ageDays != null && (
        <p
          className={`mt-1.5 text-[10px] font-medium ${
            isUrgent ? "text-warning/80" : "text-white/30"
          }`}
        >
          {urgencyLabel(t, item.ageDays)}
        </p>
      )}
    </Link>
  );
}

function EnvelopeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      className="size-4"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 7l9 6 9-6M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"
      />
    </svg>
  );
}

function UserCheckIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      className="size-4"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8 4l2 2 4-4"
      />
    </svg>
  );
}

function BriefcaseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      className="size-4"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M20 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2ZM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
      />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      className="size-4"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h6"
      />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="currentColor"
      className="size-4 rtl:rotate-180"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06L7.28 11.78a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z"
        clipRule="evenodd"
      />
    </svg>
  );
}
