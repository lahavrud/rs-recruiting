import { useTranslation } from "react-i18next";

import StatusBadge from "@/components/ui/StatusBadge";

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-copper/10 text-copper",
  APPROVED_BY_ADMIN: "bg-success/10 text-success",
  REJECTED: "bg-danger/10 text-danger",
  HIRED: "bg-hired/10 text-hired",
  JOB_CLOSED: "bg-white/8 text-white/45",
  WITHDRAWN: "bg-white/3 text-white/25",
};

interface Props {
  /** Audit row `detail` string in the `"FROM->TO"` shape written by `application.status_change`. */
  detail: string | null;
}

/** Renders the "FROM ← TO" status badge pair for an `application.status_change` audit row. */
export default function StatusChangeBadges({ detail }: Props) {
  const { t } = useTranslation("admin");
  const [statusFrom, statusTo] = (detail ?? "").split("->");

  return (
    <div className="flex flex-wrap items-center gap-2">
      <StatusBadge
        label={t(`admin:applications.statusLabels.${statusFrom}`, statusFrom)}
        colorCls={STATUS_COLORS[statusFrom] ?? "bg-white/8 text-white/45"}
      />
      <span className="text-white/30" aria-hidden>
        ←
      </span>
      <StatusBadge
        label={t(`admin:applications.statusLabels.${statusTo}`, statusTo)}
        colorCls={STATUS_COLORS[statusTo] ?? "bg-white/8 text-white/45"}
      />
    </div>
  );
}
