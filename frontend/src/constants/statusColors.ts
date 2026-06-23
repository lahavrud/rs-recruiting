import { ApplicationStatus, JobStatus } from "@/types/enums";

export const JOB_STATUS_COLORS: Record<string, string> = {
  [JobStatus.PENDING_APPROVAL]: "bg-warning/10 text-warning",
  [JobStatus.PUBLISHED]: "bg-success/10 text-success",
  [JobStatus.CLOSED]: "bg-white/8 text-white/45",
};

export const APPLICATION_STATUS_COLORS: Record<string, string> = {
  [ApplicationStatus.NEW]: "bg-copper/10 text-copper",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "bg-success/10 text-success",
  [ApplicationStatus.REJECTED]: "bg-danger/10 text-danger",
  [ApplicationStatus.HIRED]: "bg-hired/10 text-hired",
  [ApplicationStatus.JOB_CLOSED]: "bg-white/8 text-white/45",
  [ApplicationStatus.WITHDRAWN]: "bg-white/3 text-white/25",
};

export const APPLICATION_STATUS_META: Record<
  string,
  { barClass: string; dotClass: string }
> = {
  [ApplicationStatus.NEW]: {
    barClass: "bg-copper/85",
    dotClass: "bg-copper/85",
  },
  [ApplicationStatus.APPROVED_BY_ADMIN]: {
    barClass: "bg-success/85",
    dotClass: "bg-success/85",
  },
  [ApplicationStatus.HIRED]: {
    barClass: "bg-hired/85",
    dotClass: "bg-hired/85",
  },
  [ApplicationStatus.REJECTED]: {
    barClass: "bg-danger/70",
    dotClass: "bg-danger/70",
  },
};
