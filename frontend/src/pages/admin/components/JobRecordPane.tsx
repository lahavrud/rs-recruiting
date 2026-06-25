import { useTranslation } from "react-i18next";

import RecordPane from "@/components/admin/RecordPane";
import Button from "@/components/ui/Button";
import { JOB_STATUS_COLORS } from "@/constants/statusColors";
import { getJob } from "@/services/adminJobs";
import type { JobRead } from "@/types/jobs";

import { JobDetailBody } from "./JobViewBody";

interface Props {
  jobId: number | null;
  job?: JobRead;
  companyName?: string;
  companyNameById: Map<number, string>;
  onEdit: (job: JobRead) => void;
  onApprove: (job: JobRead) => void;
  onReject: (job: JobRead) => void;
  onDelete: (job: JobRead) => void;
}

export default function JobRecordPane({
  jobId,
  job,
  companyNameById,
  onEdit,
  onApprove,
  onReject,
  onDelete,
}: Props) {
  const { t } = useTranslation(["admin", "common", "publicJobs"]);

  const STATUS_LABELS: Record<string, string> = {
    PENDING_APPROVAL: t("admin:jobs.statusLabels.PENDING_APPROVAL"),
    PUBLISHED: t("admin:jobs.statusLabels.PUBLISHED"),
    CLOSED: t("admin:jobs.statusLabels.CLOSED"),
  };

  return (
    <RecordPane
      id={jobId}
      entity={job}
      fetcher={getJob}
      listPath="/admin/jobs"
      listLabel={t("admin:jobs.title")}
      crumbLabel={(j) => j.title}
      emptyHeadline={t("admin:jobs.record.emptyHeadline")}
      emptyDescription={t("admin:jobs.record.emptyDescription")}
      notFoundHeadline={t("admin:jobs.record.notFound")}
      loadErrorMessage={t("admin:jobs.loadError")}
    >
      {(j) => (
        <>
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-widest text-copper">
                {t("admin:jobs.record.eyebrow")}
              </p>
              <h2 className="mt-1 text-xl font-semibold text-white/95 @sm:text-2xl">
                {j.title}
              </h2>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {j.status === "PENDING_APPROVAL" && (
                <>
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => onApprove(j)}
                  >
                    {t("admin:jobs.approve")}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => onReject(j)}
                  >
                    {t("admin:jobs.reject")}
                  </Button>
                </>
              )}
              <Button variant="ghost" size="sm" onClick={() => onEdit(j)}>
                {t("admin:jobs.editAction")}
              </Button>
              <button
                type="button"
                onClick={() => onDelete(j)}
                aria-label={t("admin:jobs.deleteAction")}
                title={t("admin:jobs.deleteAction")}
                className="group inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-danger/30 text-danger/70 transition hover:border-danger/50 hover:bg-danger/10 hover:text-danger"
              >
                <TrashIcon className="size-4" />
              </button>
            </div>
          </div>

          <div className="border-t border-white/8 pt-4">
            <JobDetailBody
              job={j}
              statusLabels={STATUS_LABELS}
              statusColors={JOB_STATUS_COLORS}
              companyName={companyNameById.get(j.company_id)}
            />
          </div>
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
