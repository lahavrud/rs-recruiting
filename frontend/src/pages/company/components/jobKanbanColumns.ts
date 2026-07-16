import { ApplicationStatus } from "@/types/enums";

// ─── Column definitions ───────────────────────────────────────────────────────
//
// The employer pipeline, left → right. APPROVED_BY_ADMIN is the intake column
// (not droppable — applications land there from admin approval); the rest are
// the company's own stages and terminal decision. `status` values must be
// company-settable on the backend (see ApplicationStatus.company_settable).

export interface ColumnDef {
  status: string;
  labelKey: string;
  textCls: string;
  headerBg: string;
  colBg: string;
  dotCls: string;
  droppable: boolean;
  dropRingCls: string;
}

export const COLUMNS: ColumnDef[] = [
  {
    status: ApplicationStatus.APPROVED_BY_ADMIN,
    labelKey: "company:jobs.kanban.columns.APPROVED_BY_ADMIN",
    textCls: "text-copper",
    headerBg: "bg-copper/10",
    colBg: "bg-copper/[0.03]",
    dotCls: "bg-copper",
    droppable: false,
    dropRingCls: "",
  },
  {
    status: ApplicationStatus.INTERVIEWING,
    labelKey: "company:jobs.kanban.columns.INTERVIEWING",
    textCls: "text-info",
    headerBg: "bg-info/10",
    colBg: "bg-info/[0.03]",
    dotCls: "bg-info",
    droppable: true,
    dropRingCls: "ring-info/40",
  },
  {
    status: ApplicationStatus.OFFER,
    labelKey: "company:jobs.kanban.columns.OFFER",
    textCls: "text-warning",
    headerBg: "bg-warning/10",
    colBg: "bg-warning/[0.03]",
    dotCls: "bg-warning",
    droppable: true,
    dropRingCls: "ring-warning/40",
  },
  {
    status: ApplicationStatus.HIRED,
    labelKey: "company:jobs.kanban.columns.HIRED",
    textCls: "text-hired",
    headerBg: "bg-hired/10",
    colBg: "bg-hired/[0.03]",
    dotCls: "bg-hired",
    droppable: true,
    dropRingCls: "ring-hired/40",
  },
  {
    status: ApplicationStatus.REJECTED_BY_COMPANY,
    labelKey: "company:jobs.kanban.columns.REJECTED_BY_COMPANY",
    textCls: "text-danger",
    headerBg: "bg-danger/10",
    colBg: "bg-danger/[0.03]",
    dotCls: "bg-danger",
    droppable: true,
    dropRingCls: "ring-danger/40",
  },
];

export const DROPPABLE_STATUSES = new Set(
  COLUMNS.filter((c) => c.droppable).map((c) => c.status),
);
