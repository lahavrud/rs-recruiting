import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { getApplication } from "@/services/adminApplications";
import type { ApplicationWithDetails } from "@/types/candidates";

interface Props {
  applicationId: number | null;
  application?: ApplicationWithDetails;
}

/** Right-hand record pane: breadcrumb + candidate/job context. Skeleton for #892 — header, relations, and timeline land in follow-up slices. */
export default function ApplicationRecordPane({ applicationId, application }: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const [fetched, setFetched] = useState<ApplicationWithDetails | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setFetched(null);
    setNotFound(false);
    setLoadError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    if (applicationId == null || application) return;
    const ctrl = new AbortController();
    getApplication(applicationId, ctrl.signal)
      .then(setFetched)
      .catch((e) => {
        if (axios.isCancel(e)) return;
        if (axios.isAxiosError(e) && e.response?.status === 404) {
          setNotFound(true);
        } else {
          setLoadError(true);
        }
      });
    return () => ctrl.abort();
  }, [applicationId, application]);

  if (applicationId == null) {
    return (
      <EmptyState
        eyebrow={t("admin:applications.title")}
        headline={t("admin:applications.record.emptyHeadline")}
        description={t("admin:applications.record.emptyDescription")}
      />
    );
  }

  const app = application ?? fetched;

  if (!app) {
    if (notFound) {
      return (
        <EmptyState
          eyebrow={t("admin:applications.title")}
          headline={t("admin:applications.record.notFound")}
        />
      );
    }
    if (loadError) {
      return <ErrorState message={t("admin:applications.loadError")} />;
    }
    return (
      <div className="animate-pulse rounded-xl border border-white/8 bg-card p-4 sm:p-6">
        <div className="mb-4 h-3 w-32 rounded bg-white/5" />
        <div className="h-5 w-48 rounded bg-white/8" />
        <div className="mt-3 h-3 w-64 rounded bg-white/5" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/8 bg-card p-4 sm:p-6">
      <Link
        to="/admin/applications"
        className="mb-4 flex items-center gap-1.5 text-sm text-white/50 transition hover:text-copper md:hidden"
      >
        <BackChevron />
        {t("admin:applications.title")}
      </Link>

      <nav className="mb-4 hidden items-center gap-2 text-sm text-white/50 md:flex">
        <Link to="/admin/applications" className="transition hover:text-copper">
          {t("admin:applications.title")}
        </Link>
        <span aria-hidden>›</span>
        <span className="text-white/80">
          {app.candidate.full_name} → {app.job.title}
        </span>
      </nav>

      <h2 className="text-lg font-semibold text-white/90">{app.candidate.full_name}</h2>
      <p className="mt-1 text-sm text-white/50">{app.job.title}</p>

      <div className="mt-6 border-t border-white/8 pt-6">
        <p className="text-sm text-white/35">{t("admin:applications.record.comingSoon")}</p>
      </div>
    </div>
  );
}

function BackChevron() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-3.5"
      aria-hidden="true"
    >
      <path d="M6 4 L10 8 L6 12" />
    </svg>
  );
}
