import { useTranslation } from "react-i18next";

import StatusSegmentedControl, {
  type StatusSegmentConfig,
} from "@/components/admin/StatusSegmentedControl";
import { JobStatus } from "@/types/enums";

export { default as SalaryRangeField } from "@/components/ui/SalaryRangeField";
const ALL_STATUSES = [
  JobStatus.PENDING_APPROVAL,
  JobStatus.PUBLISHED,
  JobStatus.CLOSED,
];


export { default as Field } from "@/components/ui/Field";

/** Featured-toggle as a star button. Click opens a confirm dialog in the parent. */
export function FeaturedStarButton({
  isActive,
  onToggleRequest,
}: {
  isActive: boolean;
  onToggleRequest: () => void;
}) {
  const { t } = useTranslation(["admin", "common"]);
  return (
    <button
      type="button"
      onClick={onToggleRequest}
      aria-pressed={isActive}
      aria-label={t("admin:jobs.fields.featuredToggleAria")}
      title={t(isActive ? "admin:jobs.featuredOnHint" : "admin:jobs.featuredOffHint")}
      className={`inline-flex size-10 shrink-0 items-center justify-center rounded-sm border transition duration-200 active:scale-90 ${
        isActive
          ? "border-gold/60 bg-gold/15 text-gold hover:bg-gold/25"
          : "border-white/15 text-white/40 hover:border-gold/40 hover:text-gold/80"
      }`}
    >
      <svg
        viewBox="0 0 24 24"
        fill={isActive ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        className="size-5"
        aria-hidden="true"
      >
        <path d="M12 2.5l3.09 6.26 6.91 1.01-5 4.87 1.18 6.88L12 18.27l-6.18 3.25L7 14.64 2 9.77l6.91-1.01L12 2.5z" />
      </svg>
    </button>
  );
}

const STATUS_SEGMENT_CONFIG: Record<JobStatus, StatusSegmentConfig> = {
  [JobStatus.PENDING_APPROVAL]: {
    sliderCls: "bg-warning/10 border-warning/25",
    activeCls: "text-warning",
    dotCls: "bg-warning/65",
  },
  [JobStatus.PUBLISHED]: {
    sliderCls: "bg-success/10 border-success/25",
    activeCls: "text-success",
    dotCls: "bg-success/65",
  },
  [JobStatus.CLOSED]: {
    sliderCls: "bg-white/7 border-white/18",
    activeCls: "text-white/70",
    dotCls: "bg-white/40",
  },
};

/** Status as a segmented control — sliding highlight encodes selection independent of color. */
export function StatusPills({
  value,
  onChange,
}: {
  value: JobStatus;
  onChange: (s: JobStatus) => void;
}) {
  const { t } = useTranslation(["admin", "common"]);

  return (
    <StatusSegmentedControl
      statuses={ALL_STATUSES}
      value={value}
      onChange={onChange}
      config={STATUS_SEGMENT_CONFIG}
      labelFor={(s) => t(`admin:jobs.statusLabels.${s}`)}
      ariaLabel={t("admin:jobs.fields.status")}
    />
  );
}

