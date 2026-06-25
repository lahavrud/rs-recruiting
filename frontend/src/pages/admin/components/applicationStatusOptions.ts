import type { StatusSegmentConfig } from "@/components/admin/StatusSegmentedControl";
import { ApplicationStatus } from "@/types/enums";

/** Admin-settable statuses — excludes the system-driven JOB_CLOSED/WITHDRAWN. */
export const ALL_STATUSES = [
  ApplicationStatus.NEW,
  ApplicationStatus.APPROVED_BY_ADMIN,
  ApplicationStatus.REJECTED,
  ApplicationStatus.HIRED,
];

export const TERMINAL_STATUSES = new Set<string>([
  ApplicationStatus.REJECTED,
  ApplicationStatus.HIRED,
]);

/** Segment styling for the status pills, mirroring Jobs' STATUS_SEGMENT_CONFIG palette. */
export const APPLICATION_STATUS_SEGMENT_CONFIG: Record<string, StatusSegmentConfig> = {
  [ApplicationStatus.NEW]: {
    sliderCls: "bg-copper/10 border-copper/25",
    activeCls: "text-copper",
    dotCls: "bg-copper/65",
  },
  [ApplicationStatus.APPROVED_BY_ADMIN]: {
    sliderCls: "bg-success/10 border-success/25",
    activeCls: "text-success",
    dotCls: "bg-success/65",
  },
  [ApplicationStatus.REJECTED]: {
    sliderCls: "bg-danger/10 border-danger/25",
    activeCls: "text-danger",
    dotCls: "bg-danger/65",
  },
  [ApplicationStatus.HIRED]: {
    sliderCls: "bg-hired/10 border-hired/25",
    activeCls: "text-hired",
    dotCls: "bg-hired/65",
  },
};
