import { useState } from "react";

import { useTranslation } from "react-i18next";

import RecordPane from "@/components/admin/RecordPane";
import Button from "@/components/ui/Button";
import { getCompanyProfile } from "@/services/adminCompanies";
import type { CompanyProfileRead } from "@/types/auth";

import { CompanyDetailBody } from "./CompanyDetailDialog";
import CompanyJobsPanel from "./CompanyJobsPanel";

type RecordTab = "profile" | "jobs";

interface Props {
  companyId: number | null;
  company?: CompanyProfileRead;
  onEdit: (profile: CompanyProfileRead) => void;
  onDelete: (profile: CompanyProfileRead) => void;
  onApprove?: () => void;
  onReject?: () => void;
  isActing?: boolean;
}

export default function CompanyRecordPane({
  companyId,
  company,
  onEdit,
  onDelete,
  onApprove,
  onReject,
  isActing = false,
}: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const [tab, setTab] = useState<RecordTab>("profile");

  return (
    <RecordPane
      id={companyId}
      entity={company}
      fetcher={getCompanyProfile}
      listPath="/admin/companies"
      listLabel={t("admin:companies.title")}
      crumbLabel={(p) => p.name}
      emptyHeadline={t("admin:companies.record.emptyHeadline")}
      emptyDescription={t("admin:companies.record.emptyDescription")}
      notFoundHeadline={t("admin:companies.record.notFound")}
      loadErrorMessage={t("admin:companies.active.loadError")}
    >
      {(profile) => (
        <>
          {/* ── Header ───────────────────────────────────────── */}
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-widest text-copper">
                {t("admin:companies.record.eyebrow")}
              </p>
              <h2 className="mt-1 text-xl font-semibold text-white/95 @sm:text-2xl">
                {profile.name}
              </h2>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {onApprove && (
                <Button variant="success" size="sm" onClick={onApprove} disabled={isActing}>
                  {t("admin:reviewQueue.approved")}
                </Button>
              )}
              {onReject && (
                <Button variant="danger" size="sm" onClick={onReject} disabled={isActing}>
                  {t("admin:reviewQueue.rejected")}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => onEdit(profile)}>
                {t("admin:companies.editAction")}
              </Button>
              {profile.contact_email && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.open(`mailto:${profile.contact_email}`, "_self")}
                >
                  {t("admin:companies.emailAction")}
                </Button>
              )}
              <button
                type="button"
                onClick={() => onDelete(profile)}
                aria-label={t("admin:companies.deleteAction")}
                title={t("admin:companies.deleteAction")}
                className="group inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-danger/30 text-danger/70 transition hover:border-danger/50 hover:bg-danger/10 hover:text-danger"
              >
                <TrashIcon className="size-4" />
              </button>
            </div>
          </div>

          {/* ── Tab bar ──────────────────────────────────────── */}
          <div className="mb-4 flex border-b border-white/8">
            {(["profile", "jobs"] as RecordTab[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`px-4 pb-2 text-sm font-medium transition ${
                  tab === key
                    ? "border-b-2 border-copper text-copper"
                    : "text-white/45 hover:text-white/75"
                }`}
              >
                {t(`admin:companies.record.tabs.${key}`)}
              </button>
            ))}
          </div>

          {/* ── Tab content ──────────────────────────────────── */}
          {tab === "profile" ? (
            <CompanyDetailBody profile={profile} />
          ) : (
            <CompanyJobsPanel companyId={profile.id} />
          )}
        </>
      )}
    </RecordPane>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M3.75 4.5 L4.25 13 a1 1 0 0 0 1 0.9 h5.5 a1 1 0 0 0 1 -0.9 L12.25 4.5" />
      <path d="M6.5 7.5 V11.5 M9.5 7.5 V11.5" />
      <g className="origin-[3px_4.5px] transition-transform duration-200 ease-out group-hover:-rotate-[25deg]">
        <path d="M3 4.5 H13" />
        <path d="M5.5 4.5 V3 a1 1 0 0 1 1 -1 h3 a1 1 0 0 1 1 1 V4.5" />
      </g>
    </svg>
  );
}
