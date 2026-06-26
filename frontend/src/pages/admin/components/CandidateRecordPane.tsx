import { useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import RecordPane from "@/components/admin/RecordPane";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
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

/** Right-hand record pane: identity header with primary actions. Composes the shared `RecordPane` shell. */
export default function CandidateRecordPane({ candidateId, candidate, onDeleted }: Props) {
  const { t } = useTranslation(['admin', 'common']);
  const navigate = useNavigate();
  const toast = useToast();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDeleteConfirm(recordId: number) {
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
    <RecordPane
      id={candidateId}
      entity={candidate}
      fetcher={getCandidate}
      listPath="/admin/candidates"
      listLabel={t("admin:candidates.title")}
      crumbLabel={(c) => c.full_name}
      emptyHeadline={t("admin:candidates.record.emptyHeadline")}
      emptyDescription={t("admin:candidates.record.emptyDescription")}
      notFoundHeadline={t("admin:candidates.record.notFound")}
      loadErrorMessage={t("admin:candidates.loadError")}
    >
      {(c) => (
        <>
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
                {c.resume_summary && (
                  <p className="mt-1.5 text-sm leading-relaxed text-white/50">
                    {c.resume_summary}
                  </p>
                )}
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
            onConfirm={() => handleDeleteConfirm(c.id)}
          />
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
