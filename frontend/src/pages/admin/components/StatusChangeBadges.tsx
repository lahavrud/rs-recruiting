import { useTranslation } from "react-i18next";

import StatusBadge from "@/components/ui/StatusBadge";

const STATUS_COLORS: Record<string, string> = {
  PENDING_ADMIN_REVIEW: "bg-copper/10 text-copper",
  APPROVED_BY_ADMIN: "bg-success/10 text-success",
  INTERVIEWING: "bg-info/10 text-info",
  OFFER: "bg-warning/10 text-warning",
  REJECTED_BY_COMPANY: "bg-danger/10 text-danger",
  REJECTED_BY_ADMIN: "bg-danger/10 text-danger",
  HIRED: "bg-hired/10 text-hired",
  JOB_CLOSED: "bg-white/8 text-white/45",
  WITHDRAWN: "bg-white/3 text-white/25",
};

interface Props {
  /** Audit row `detail` string in the `"FROM->TO"` shape written by `application.status_change`. */
  detail: string | null;
}

const NEUTRAL_COLOR = "bg-white/8 text-white/45";

/**
 * Renders the "FROM ← TO" status badge pair for an `application.status_change` audit row.
 *
 * Rows written before every writer used "FROM->TO" (job-close cascades, the
 * stranded-application backfill) read e.g. "JOB_CLOSED (cascade, job 7)": no
 * previous status was recorded, so only the new one is shown.
 */
export default function StatusChangeBadges({ detail }: Props) {
  const { t } = useTranslation("admin");
  const text = detail ?? "";
  const [statusFrom, statusTo] = text.includes("->")
    ? text.split("->")
    : [null, text.split(" ")[0]];

  const badge = (status: string) => (
    <StatusBadge
      label={t(`admin:applications.statusLabels.${status}`, status)}
      colorCls={STATUS_COLORS[status] ?? NEUTRAL_COLOR}
    />
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      {statusFrom !== null && (
        <>
          {badge(statusFrom)}
          <span className="text-white/30" aria-hidden>
            ←
          </span>
        </>
      )}
      {badge(statusTo)}
    </div>
  );
}
