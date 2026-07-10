import { ApplicationStatus, JobStatus } from "@/types/enums";

export const JOB_STATUS_COLORS: Record<string, string> = {
  [JobStatus.PENDING_APPROVAL]: "bg-warning/10 text-warning",
  [JobStatus.PUBLISHED]: "bg-success/10 text-success",
  [JobStatus.CLOSED]: "bg-white/8 text-white/45",
};

export const APPLICATION_STATUS_COLORS: Record<string, string> = {
  [ApplicationStatus.PENDING_ADMIN_REVIEW]: "bg-copper/10 text-copper",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "bg-success/10 text-success",
  [ApplicationStatus.INTERVIEWING]: "bg-info/10 text-info",
  [ApplicationStatus.OFFER]: "bg-warning/10 text-warning",
  [ApplicationStatus.HIRED]: "bg-hired/10 text-hired",
  [ApplicationStatus.REJECTED_BY_COMPANY]: "bg-danger/10 text-danger",
  [ApplicationStatus.REJECTED_BY_ADMIN]: "bg-danger/10 text-danger",
  [ApplicationStatus.JOB_CLOSED]: "bg-white/8 text-white/45",
  [ApplicationStatus.WITHDRAWN]: "bg-white/3 text-white/25",
};

export const APPLICATION_STATUS_META: Record<
  string,
  { barClass: string; dotClass: string }
> = {
  [ApplicationStatus.PENDING_ADMIN_REVIEW]: {
    barClass: "bg-copper/85",
    dotClass: "bg-copper/85",
  },
  [ApplicationStatus.APPROVED_BY_ADMIN]: {
    barClass: "bg-success/85",
    dotClass: "bg-success/85",
  },
  [ApplicationStatus.INTERVIEWING]: {
    barClass: "bg-info/85",
    dotClass: "bg-info/85",
  },
  [ApplicationStatus.OFFER]: {
    barClass: "bg-warning/85",
    dotClass: "bg-warning/85",
  },
  [ApplicationStatus.HIRED]: {
    barClass: "bg-hired/85",
    dotClass: "bg-hired/85",
  },
  [ApplicationStatus.REJECTED_BY_COMPANY]: {
    barClass: "bg-danger/70",
    dotClass: "bg-danger/70",
  },
  [ApplicationStatus.REJECTED_BY_ADMIN]: {
    barClass: "bg-danger/70",
    dotClass: "bg-danger/70",
  },
};
