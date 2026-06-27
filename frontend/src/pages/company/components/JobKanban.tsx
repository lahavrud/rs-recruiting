import { useEffect, useRef, useState } from "react";

import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import CandidateDetailDrawer from "@/pages/company/components/CandidateDetailDrawer";
import { getJobApplications, updateApplicationStatus } from "@/services/companyJobs";
import type { CompanyApplicationRead } from "@/types/companies";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

// ─── Column config (3 columns only — no NEW / WITHDRAWN) ─────────────────────

interface ColumnDef {
  status: string;
  labelKey: string;
  textCls: string;
  headerBg: string;
  colBg: string;
  dotCls: string;
  droppable: boolean;
  dropRingCls: string;
}

const COLUMNS: ColumnDef[] = [
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
    status: ApplicationStatus.REJECTED,
    labelKey: "company:jobs.kanban.columns.REJECTED",
    textCls: "text-danger",
    headerBg: "bg-danger/10",
    colBg: "bg-danger/[0.03]",
    dotCls: "bg-danger",
    droppable: true,
    dropRingCls: "ring-danger/40",
  },
];

const DROPPABLE_STATUSES = new Set(
  COLUMNS.filter((c) => c.droppable).map((c) => c.status),
);

const PCT = 100;
const SCORE_HIGH = 80;
const SCORE_MID = 65;
const FLOAT_ROTATE = "rotate(1.5deg)";
const FLOAT_W = 272;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();
}

const AVATAR_PALETTE = [
  "bg-copper/20 text-copper",
  "bg-info/20 text-info",
  "bg-hired/20 text-hired",
  "bg-warning/20 text-warning",
];

function avatarCls(id: number) {
  return AVATAR_PALETTE[id % AVATAR_PALETTE.length];
}

// ─── Card (shared between column and floating) ────────────────────────────────

interface CardProps {
  app: CompanyApplicationRead;
  floating?: boolean;
}

function Card({ app, floating }: CardProps) {
  const { t } = useTranslation("company");
  const pct = app.match_score != null ? Math.round(app.match_score * PCT) : null;
  const barColor =
    pct == null ? ""
    : pct >= SCORE_HIGH ? "bg-success"
    : pct >= SCORE_MID ? "bg-copper"
    : "bg-warning";

  return (
    <div
      dir="rtl"
      className={`rounded-xl border bg-card p-4 space-y-2.5 select-none
        ${floating
          ? "border-white/20 shadow-2xl shadow-black/60"
          : "border-white/8 shadow-sm"
        }`}
    >
      {/* Avatar + name */}
      <div className="flex items-center gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold ${avatarCls(app.candidate.id)}`}
        >
          {initials(app.candidate.full_name)}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-white/90">
            {app.candidate.full_name}
          </p>
          <p className="truncate text-[11px] text-white/40">{app.candidate.email}</p>
        </div>
      </div>

      {/* Score bar */}
      {pct != null && (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
            <div
              className={`h-full rounded-full ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="shrink-0 text-[10px] tabular-nums text-white/40">{pct}%</span>
        </div>
      )}

      {/* AI review */}
      {app.ai_review && (
        <p className="line-clamp-2 text-[11px] leading-relaxed text-white/45 italic">
          {app.ai_review}
        </p>
      )}

      <p className="text-[10px] text-white/20">
        {t("company:jobs.kanban.appliedOn")}
        {formatDate(app.created_at)}
      </p>
    </div>
  );
}

// ─── JobKanban ────────────────────────────────────────────────────────────────

interface DragState {
  app: CompanyApplicationRead;
  x: number;
  y: number;
  offsetX: number;
  offsetY: number;
  overStatus: string | null;
}

interface JobKanbanProps {
  jobId: number;
}

export default function JobKanban({ jobId }: JobKanbanProps) {
  const { t } = useTranslation("company");
  const [applications, setApplications] = useState<CompanyApplicationRead[] | null>(null);
  const [error, setError] = useState(false);
  const [selectedApp, setSelectedApp] = useState<CompanyApplicationRead | null>(null);
  const [dragRender, setDragRender] = useState<DragState | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const colRefs = useRef<Partial<Record<string, HTMLDivElement>>>({});

  useEffect(() => {
    let cancelled = false;
    getJobApplications(jobId)
      .then((apps) => { if (!cancelled) setApplications(apps); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [jobId]);

  // Attach/detach window pointer listeners only while a drag is active
  const isDragging = dragRender !== null;
  useEffect(() => {
    if (!isDragging) return;

    function getOverStatus(x: number, y: number): string | null {
      for (const status of DROPPABLE_STATUSES) {
        const el = colRefs.current[status];
        if (!el) continue;
        const r = el.getBoundingClientRect();
        if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return status;
      }
      return null;
    }

    function onMove(e: PointerEvent) {
      if (!dragRef.current) return;
      const next: DragState = {
        ...dragRef.current,
        x: e.clientX,
        y: e.clientY,
        overStatus: getOverStatus(e.clientX, e.clientY),
      };
      dragRef.current = next;
      setDragRender({ ...next });
    }

    function onUp() {
      const state = dragRef.current;
      dragRef.current = null;
      setDragRender(null);
      if (!state || !state.overStatus || state.overStatus === state.app.status) return;
      const { app, overStatus } = state;
      updateApplicationStatus(jobId, app.id, overStatus)
        .then((updated) => {
          setApplications((prev) =>
            prev ? prev.map((a) => (a.id === app.id ? updated : a)) : prev,
          );
          setSelectedApp((prev) => (prev?.id === app.id ? updated : prev));
        })
        .catch(() => {});
    }

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [isDragging, jobId]);

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>, app: CompanyApplicationRead) {
    if (e.button !== 0) return;
    e.preventDefault();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const state: DragState = {
      app,
      x: e.clientX,
      y: e.clientY,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top,
      overStatus: null,
    };
    dragRef.current = state;
    setDragRender({ ...state });
  }

  // ─── States ─────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <p className="py-10 text-center text-sm text-danger">
        {t("company:jobs.kanban.loadError")}
      </p>
    );
  }

  if (applications === null) {
    return (
      <div className="grid grid-cols-3 gap-4">
        {COLUMNS.map((col) => (
          <div
            key={col.status}
            className="flex flex-col rounded-xl border border-white/6"
          >
            <div className={`rounded-t-xl border-b border-white/6 px-4 py-3 ${col.headerBg}`}>
              <div className="h-3 w-16 animate-pulse rounded bg-white/10" />
            </div>
            <div className={`space-y-2 rounded-b-xl p-3 min-h-40 ${col.colBg}`}>
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 animate-pulse rounded-xl bg-white/4" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (applications.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-white/8 py-16 text-center text-sm text-white/25">
        {t("company:jobs.kanban.empty")}
      </div>
    );
  }

  const byStatus = Object.fromEntries(
    COLUMNS.map(({ status }) => [status, applications.filter((a) => a.status === status)]),
  );

  return (
    <>
      <p className="mb-3 text-xs text-white/30">
        {t("company:jobs.kanban.totalCandidates", { count: applications.length })}
      </p>

      <div className={`grid grid-cols-3 gap-4 ${isDragging ? "cursor-grabbing" : ""}`}>
        {COLUMNS.map((col) => {
          const cards = byStatus[col.status] ?? [];
          const isOver = dragRender?.overStatus === col.status;

          return (
            <div
              key={col.status}
              ref={(el) => { colRefs.current[col.status] = el ?? undefined; }}
              className={`flex flex-col rounded-xl border transition-all duration-150
                ${isOver ? `border-white/20 ring-1 ${col.dropRingCls} shadow-lg` : "border-white/6"}
              `}
            >
              {/* Header */}
              <div
                className={`flex items-center justify-between rounded-t-xl border-b border-white/6 px-4 py-3 ${col.headerBg}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${col.dotCls}`} />
                  <span className={`text-[11px] font-semibold uppercase tracking-widest ${col.textCls}`}>
                    {t(col.labelKey)}
                  </span>
                </div>
                <span
                  className={`min-w-5 rounded-full px-1.5 py-px text-center text-[11px] font-bold tabular-nums
                    ${cards.length > 0 ? `${col.headerBg} ${col.textCls}` : "text-white/20"}`}
                >
                  {cards.length}
                </span>
              </div>

              {/* Column body */}
              <div className={`flex flex-1 flex-col gap-2 rounded-b-xl p-3 min-h-40 ${col.colBg}`}>
                {cards.map((app) => {
                  const isFloating = dragRender?.app.id === app.id;
                  return (
                    <div
                      key={app.id}
                      onPointerDown={(e) => handlePointerDown(e, app)}
                      onClick={() => { if (!isDragging) setSelectedApp(app); }}
                      className={`transition-opacity duration-150 ${
                        isFloating ? "opacity-0 pointer-events-none" : "cursor-grab hover:opacity-90"
                      }`}
                      style={{ touchAction: "none" }}
                    >
                      <Card app={app} />
                    </div>
                  );
                })}

                {col.droppable && cards.length === 0 && !isDragging && (
                  <div className="flex flex-1 items-center justify-center py-8">
                    <span className="text-[11px] text-white/15">—</span>
                  </div>
                )}

                {col.droppable && isDragging && (
                  <div
                    className={`flex-1 rounded-lg border-2 border-dashed py-6 text-center text-[11px] transition-colors
                      ${isOver ? `border-current ${col.textCls} bg-white/3` : "border-white/10 text-white/20"}`}
                  >
                    {isOver ? t("company:jobs.kanban.dropHere") : ""}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Floating card — physically follows the cursor */}
      {dragRender &&
        createPortal(
          <div
            style={{
              position: "fixed",
              left: dragRender.x - dragRender.offsetX,
              top: dragRender.y - dragRender.offsetY,
              width: FLOAT_W,
              pointerEvents: "none",
              zIndex: 9999,
              transform: FLOAT_ROTATE,
            }}
          >
            <Card app={dragRender.app} floating />
          </div>,
          document.body,
        )}

      <CandidateDetailDrawer app={selectedApp} onClose={() => setSelectedApp(null)} />
    </>
  );
}
