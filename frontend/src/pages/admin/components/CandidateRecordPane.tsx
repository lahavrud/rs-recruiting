import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import Eyebrow from "@/components/ui/Eyebrow";
import { useToast } from "@/hooks/useToast";
import { deleteCandidate, getCandidate } from "@/services/adminCandidates";
import type { CandidateProfileRead } from "@/types/candidates";

import CandidateActivityPanel from "./CandidateActivityPanel";
import CandidateApplicationsPanel from "./CandidateApplicationsPanel";
import CandidateContactInfo from "./CandidateContactInfo";
import CandidateMatchesPanel from "./CandidateMatchesPanel";

interface Props {
  candidateId: number | null;
  candidate?: CandidateProfileRead;
  onDeleted: (id: number) => void;
}

/** Right-hand record pane: breadcrumb + identity header with primary actions. Applications and timeline land in follow-up slices. */
export default function CandidateRecordPane({ candidateId, candidate, onDeleted }: Props) {
  const { t } = useTranslation(['admin', 'common']);
  const navigate = useNavigate();
  const toast = useToast();
  const [fetched, setFetched] = useState<CandidateProfileRead | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  const recordId = c.id;

  async function handleDeleteConfirm() {
    setDeleting(true);
    try {
      await deleteCandidate(recordId);
      toast.success(t("admin:candidates.deletedToast"));
      setDeleteOpen(false);
      onDeleted(recordId);
      navigate("/admin/candidates");
    } catch {
      toast.error(t("admin:candidates.errors.deleteFailed"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="@container rounded-xl border border-white/8 bg-card p-4 sm:p-6">
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

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-copper/10 text-lg font-semibold text-copper @sm:size-14 @sm:text-xl">
            {c.full_name.charAt(0)}
          </div>
          <div className="min-w-0 flex-1">
            <Eyebrow>{t("admin:candidates.record.eyebrow")}</Eyebrow>
            <h2 className="mt-1 text-xl font-semibold text-white/95 @sm:text-2xl @lg:text-3xl">
              {c.full_name}
            </h2>
            <div className="mt-3">
              <CandidateContactInfo candidate={c} />
            </div>
          </div>
        </div>

        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            aria-label={t("admin:candidates.deleteAction")}
            title={t("admin:candidates.deleteAction")}
            className="group inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-danger/30 text-danger/70 transition hover:border-danger/50 hover:bg-danger/10 hover:text-danger"
          >
            <TrashIcon className="size-4" />
          </button>
        </div>
      </div>

      <div className="mt-6 border-t border-white/8 pt-6">
        <CandidateApplicationsPanel candidateId={c.id} />
      </div>

      <div className="mt-6 border-t border-white/8 pt-6">
        <CandidateMatchesPanel candidateId={c.id} />
      </div>

      <div className="mt-6 border-t border-white/8 pt-6">
        <CandidateActivityPanel candidateId={c.id} />
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t("admin:candidates.deleteConfirmTitle", { name: c.full_name })}
        message={t("admin:candidates.deleteConfirmMessage")}
        confirmLabel={t("admin:candidates.deleteConfirmYes")}
        variant="danger"
        isPending={deleting}
        onConfirm={handleDeleteConfirm}
      />
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
      {/* can body — stays put */}
      <path d="M3.75 4.5 L4.25 13 a1 1 0 0 0 1 0.9 h5.5 a1 1 0 0 0 1 -0.9 L12.25 4.5" />
      <path d="M6.5 7.5 V11.5 M9.5 7.5 V11.5" />
      {/* lid + handle — hinges open on hover */}
      <g className="origin-[3px_4.5px] transition-transform duration-200 ease-out group-hover:-rotate-[25deg]">
        <path d="M3 4.5 H13" />
        <path d="M5.5 4.5 V3 a1 1 0 0 1 1 -1 h3 a1 1 0 0 1 1 1 V4.5" />
      </g>
    </svg>
  );
}
