/**
 * Shared types + visual metadata for the triage flow.
 * The Decision type intentionally narrows ApplicationStatus to the values
 * the reviewer can act on — everything else (NEW, HIRED) is unreachable here.
 */

export type Decision = "APPROVED_BY_ADMIN" | "REJECTED_BY_ADMIN";

/**
 * Single source of truth for everything per-decision: labels, colors,
 * icons, banner tones. Consumers (strip, banner, toast, summary) read
 * from here so adding a new Decision later (e.g. INTERVIEWING) is a
 * one-place change.
 */
export const DECISION_META: Record<
  Decision,
  {
    /** i18n key — short status word (e.g. "אושר"). Reused as the chip aria. */
    shortLabelKey: string;
    /** i18n key — sentence form used by the revisit banner + undo toast. */
    bannerLabelKey: string;
    /** i18n key — plural label used by the summary screen tile. */
    summaryLabelKey: string;
    /** Text color on dark surfaces */
    text: string;
    /** Border color for outlines (banner, toast accent) */
    border: string;
    /** Soft background tint — used by the revisit banner */
    bgTint: string;
    /** Background + border combo for the strip chip */
    chip: string;
    /** Icon name — components resolve to the actual SVG component */
    icon: "check" | "close";
  }
> = {
  APPROVED_BY_ADMIN: {
    shortLabelKey: "admin:applications.statusLabels.APPROVED_BY_ADMIN",
    bannerLabelKey: "admin:applications.triage.bannerApproved",
    summaryLabelKey: "admin:applications.triage.summaryApprovedLabel",
    text: "text-success",
    border: "border-success/40",
    bgTint: "bg-success/10",
    chip: "border border-success/40 bg-success/15 hover:bg-success/25",
    icon: "check",
  },
  REJECTED_BY_ADMIN: {
    shortLabelKey: "admin:applications.statusLabels.REJECTED_BY_ADMIN",
    bannerLabelKey: "admin:applications.triage.bannerRejected",
    summaryLabelKey: "admin:applications.triage.summaryRejectedLabel",
    text: "text-danger",
    border: "border-danger/40",
    bgTint: "bg-danger/10",
    chip: "border border-danger/40 bg-danger/15 hover:bg-danger/25",
    icon: "close",
  },
};

/** Chip background when no decision exists yet (undecided / current). */
export const UNDECIDED_CHIP_BG =
  "border border-white/10 bg-card/40 hover:border-white/25";

/** he-IL short date + time, used in the candidate header. */
export function formatTriageDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
