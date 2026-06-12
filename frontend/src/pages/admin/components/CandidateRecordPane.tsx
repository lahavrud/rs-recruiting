import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import axios from "axios";
import { getCandidate } from "@/services/adminCandidates";
import type { CandidateProfileRead } from "@/types/api";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import CandidateContactInfo from "./CandidateContactInfo";

interface Props {
  candidateId: number | null;
  candidate?: CandidateProfileRead;
}

/** Right-hand record pane: breadcrumb + identity. Skeleton for #876 — applications and timeline land in follow-up slices. */
export default function CandidateRecordPane({ candidateId, candidate }: Props) {
  const { t } = useTranslation(['admin', 'common']);
  const [fetched, setFetched] = useState<CandidateProfileRead | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setFetched(null);
    setNotFound(false);
    setLoadError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    if (candidateId == null || candidate) return;
    const ctrl = new AbortController();
    getCandidate(candidateId, ctrl.signal)
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
  }, [candidateId, candidate]);

  if (candidateId == null) {
    return (
      <EmptyState
        eyebrow={t("admin:candidates.title")}
        headline={t("admin:candidates.record.emptyHeadline")}
        description={t("admin:candidates.record.emptyDescription")}
      />
    );
  }

  const c = candidate ?? fetched;

  if (!c) {
    if (notFound) {
      return (
        <EmptyState
          eyebrow={t("admin:candidates.title")}
          headline={t("admin:candidates.record.notFound")}
        />
      );
    }
    if (loadError) {
      return <ErrorState message={t("admin:candidates.loadError")} />;
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
        to="/admin/candidates"
        className="mb-4 flex items-center gap-1.5 text-sm text-white/50 transition hover:text-copper md:hidden"
      >
        <BackChevron />
        {t("admin:candidates.title")}
      </Link>

      <nav className="mb-4 hidden items-center gap-2 text-sm text-white/50 md:flex">
        <Link to="/admin/candidates" className="transition hover:text-copper">
          {t("admin:candidates.title")}
        </Link>
        <span aria-hidden>›</span>
        <span className="text-white/80">{c.full_name}</span>
      </nav>

      <h2 className="text-lg font-semibold text-white/90">{c.full_name}</h2>
      <div className="mt-2">
        <CandidateContactInfo candidate={c} />
      </div>

      <div className="mt-6 border-t border-white/8 pt-6">
        <p className="text-sm text-white/35">{t("admin:candidates.record.comingSoon")}</p>
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
