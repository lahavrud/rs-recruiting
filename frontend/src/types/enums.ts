/**
 * Enum-equivalent const objects mirroring backend src/enums.py.
 * Uses `as const` objects instead of TS enums — required by TS 6.0
 * with erasableSyntaxOnly enabled (enums emit runtime code).
 */

export const UserRole = {
  ADMIN: "ADMIN",
  COMPANY: "COMPANY",
  CANDIDATE: "CANDIDATE",
} as const;
export type UserRole = (typeof UserRole)[keyof typeof UserRole];

export const JobStatus = {
  PENDING_APPROVAL: "PENDING_APPROVAL",
  PUBLISHED: "PUBLISHED",
  CLOSED: "CLOSED",
} as const;
export type JobStatus = (typeof JobStatus)[keyof typeof JobStatus];

export const ApplicationStatus = {
  NEW: "NEW",
  APPROVED_BY_ADMIN: "APPROVED_BY_ADMIN",
  REJECTED: "REJECTED",
  HIRED: "HIRED",
  WITHDRAWN: "WITHDRAWN",
  JOB_CLOSED: "JOB_CLOSED",
} as const;
export type ApplicationStatus =
  (typeof ApplicationStatus)[keyof typeof ApplicationStatus];

export const InviteTokenStatus = {
  PENDING: "PENDING",
  USED: "USED",
  EXPIRED: "EXPIRED",
  REVOKED: "REVOKED",
} as const;
export type InviteTokenStatus =
  (typeof InviteTokenStatus)[keyof typeof InviteTokenStatus];

export const MatchSuggestionStatus = {
  DISMISSED: "DISMISSED",
  PUSHED: "PUSHED",
} as const;
export type MatchSuggestionStatus =
  (typeof MatchSuggestionStatus)[keyof typeof MatchSuggestionStatus];
