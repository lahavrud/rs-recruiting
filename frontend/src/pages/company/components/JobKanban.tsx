import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import CandidateDetailDrawer from "@/pages/company/components/CandidateDetailDrawer";
import { PCT_MULTIPLIER, scoreBarColor } from "@/pages/company/components/scoreUtils";
import { getJobApplications, updateApplicationStatus } from "@/services/companyJobs";
import type { CompanyApplicationRead } from "@/types/companies";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

// ─── Column definitions ───────────────────────────────────────────────────────

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

const DROPPABLE_STATUSES = new Set(COLUMNS.filter((c) => c.droppable).map((c) => c.status));

// ─── Constants ────────────────────────────────────────────────────────────────

const ORDER_KEY = (jobId: number) => `kanban_order_${jobId}`;
const FLIP_DURATION = "280ms";
const FLIP_EASE = "cubic-bezier(0.2,0,0,1)";
const FLIP_THRESHOLD = 2;
const CLICK_THRESHOLD = 5;
const SCROLL_ZONE = 80;
const SCROLL_SPEED_MAX = 15;

// ─── Order helpers ────────────────────────────────────────────────────────────

function loadOrder(jobId: number): Partial<Record<string, number[]>> {
  try {
    const raw = localStorage.getItem(ORDER_KEY(jobId));
    return raw ? (JSON.parse(raw) as Partial<Record<string, number[]>>) : {};
  } catch {
    return {};
  }
}

function persistOrder(jobId: number, order: Record<string, number[]>) {
  try {
    localStorage.setItem(ORDER_KEY(jobId), JSON.stringify(order));
  } catch {
    /* ignore */
  }
}

function buildOrder(
  apps: CompanyApplicationRead[],
  stored: Partial<Record<string, number[]>>,
): Record<string, number[]> {
  return Object.fromEntries(
    COLUMNS.map(({ status }) => {
      const ids = apps.filter((a) => a.status === status).map((a) => a.id);
      const saved = stored[status] ?? [];
      return [status, [...saved.filter((id) => ids.includes(id)), ...ids.filter((id) => !saved.includes(id))]];
    }),
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const AVATAR_PALETTE = [
  "bg-copper/20 text-copper",
  "bg-info/20 text-info",
  "bg-hired/20 text-hired",
  "bg-warning/20 text-warning",
];

function cardInitials(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();
}

function avatarCls(id: number) {
  return AVATAR_PALETTE[id % AVATAR_PALETTE.length];
}

// ─── Card ─────────────────────────────────────────────────────────────────────

function Card({ app, floating }: { app: CompanyApplicationRead; floating?: boolean }) {
  const { t } = useTranslation("company");
  const pct = app.match_score != null ? Math.round(app.match_score * PCT_MULTIPLIER) : null;
  const barColor = pct == null ? "" : scoreBarColor(pct);

  return (
    <div
      dir="rtl"
      className={`rounded-xl border bg-card p-4 select-none space-y-2.5 ${
        floating ? "border-white/20 shadow-2xl shadow-black/70" : "border-white/8 shadow-sm"
      }`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold ${avatarCls(app.candidate.id)}`}
        >
          {cardInitials(app.candidate.full_name)}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-white/90">{app.candidate.full_name}</p>
          <p className="truncate text-[11px] text-white/40">{app.candidate.email}</p>
        </div>
      </div>

      {pct != null && (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="shrink-0 text-[10px] tabular-nums text-white/40">{pct}%</span>
        </div>
      )}

      {app.ai_review && (
        <p className="line-clamp-2 text-[11px] leading-relaxed text-white/45 italic">{app.ai_review}</p>
      )}

      <p className="text-[10px] text-white/20">
        {t("company:jobs.kanban.appliedOn")}
        {formatDate(app.created_at)}
      </p>
    </div>
  );
}

// ─── Drag state ───────────────────────────────────────────────────────────────

interface DragState {
  app: CompanyApplicationRead;
  startStatus: string;
  startX: number;
  startY: number;
  x: number;
  y: number;
  offsetX: number;
  offsetY: number;
  cardWidth: number;
  overStatus: string | null;
  dropIndex: number;
}

// ─── JobKanban ────────────────────────────────────────────────────────────────

export default function JobKanban({ jobId }: { jobId: number }) {
  const { t } = useTranslation("company");
  const [applications, setApplications] = useState<CompanyApplicationRead[] | null>(null);
  const [order, setOrder] = useState<Record<string, number[]>>({});
  const [error, setError] = useState(false);
  const [selectedApp, setSelectedApp] = useState<CompanyApplicationRead | null>(null);
  const [dragRender, setDragRender] = useState<DragState | null>(null);

  const dragRef = useRef<DragState | null>(null);
  const orderRef = useRef<Record<string, number[]>>({});
  const colRefs = useRef<Partial<Record<string, HTMLDivElement>>>({});
  const cardElsRef = useRef(new Map<number, HTMLElement>());
  const prevRectsRef = useRef(new Map<number, DOMRect>());
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const scrollRafRef = useRef(0);
  const scrollDeltaRef = useRef(0);
  const pointerPosRef = useRef({ x: 0, y: 0 });
  // Stores the active drag cleanup so unmount mid-drag doesn't leak listeners.
  const dragCleanupRef = useRef<(() => void) | null>(null);

  function applyOrder(fn: (prev: Record<string, number[]>) => Record<string, number[]>) {
    setOrder((prev) => {
      const next = fn(prev);
      orderRef.current = next;
      return next;
    });
  }

  function snapshot(excludeId?: number) {
    prevRectsRef.current = new Map();
    for (const [id, el] of cardElsRef.current) {
      if (id === excludeId) continue;
      prevRectsRef.current.set(id, el.getBoundingClientRect());
    }
  }

  // FLIP: animate cards from old positions to new positions after a reorder.
  // Scoped to [order] so it only fires when cards actually move, not on every drag-move render.
  useLayoutEffect(() => {
    const prev = prevRectsRef.current;
    if (prev.size === 0) return;
    prevRectsRef.current = new Map();
    for (const [id, el] of cardElsRef.current) {
      const p = prev.get(id);
      if (!p) continue;
      const dy = p.top - el.getBoundingClientRect().top;
      if (Math.abs(dy) < FLIP_THRESHOLD) continue;
      el.style.transform = `translateY(${dy}px)`;
      el.style.transition = "";
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.style.transform = "";
          el.style.transition = `transform ${FLIP_DURATION} ${FLIP_EASE}`;
        });
      });
    }
  }, [order]);

  // Remove window listeners if the component unmounts during an active drag.
  useEffect(() => {
    return () => { dragCleanupRef.current?.(); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getJobApplications(jobId)
      .then((apps) => {
        if (cancelled) return;
        const stored = loadOrder(jobId);
        const built = buildOrder(apps, stored);
        orderRef.current = built;
        setApplications(apps);
        setOrder(built);
      })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [jobId]);

  function hitTest(x: number, y: number, draggingId: number): { status: string | null; idx: number } {
    for (const col of COLUMNS) {
      const el = colRefs.current[col.status];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) continue;
      const siblings = [...el.querySelectorAll<HTMLElement>("[data-card-id]")].filter(
        (ce) => Number(ce.getAttribute("data-card-id")) !== draggingId,
      );
      let idx = siblings.length;
      for (let i = 0; i < siblings.length; i++) {
        const cr = siblings[i].getBoundingClientRect();
        if (y < cr.top + cr.height / 2) { idx = i; break; }
      }
      return { status: col.status, idx };
    }
    return { status: null, idx: 0 };
  }

  const isDragging = dragRender !== null;

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>, app: CompanyApplicationRead) {
    if (e.button !== 0) return;
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const startStatus = COLUMNS.find((c) => (orderRef.current[c.status] ?? []).includes(app.id))?.status ?? app.status;
    const state: DragState = {
      app,
      startStatus,
      startX: e.clientX,
      startY: e.clientY,
      x: e.clientX,
      y: e.clientY,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top,
      cardWidth: rect.width,
      overStatus: startStatus,
      dropIndex: 0,
    };
    dragRef.current = state;

    function tick() {
      const delta = scrollDeltaRef.current;
      const scroller = scrollerRef.current;
      if (delta === 0 || !scroller) { scrollRafRef.current = 0; return; }
      scroller.scrollLeft += delta;
      const s = dragRef.current;
      if (s) {
        const { x, y } = pointerPosRef.current;
        const { status, idx } = hitTest(x, y, s.app.id);
        const next: DragState = { ...s, overStatus: status, dropIndex: idx };
        dragRef.current = next;
        setDragRender({ ...next });
      }
      scrollRafRef.current = requestAnimationFrame(tick);
    }

    function onMove(ev: PointerEvent) {
      const s = dragRef.current;
      if (!s) return;
      pointerPosRef.current = { x: ev.clientX, y: ev.clientY };
      const { status, idx } = hitTest(ev.clientX, ev.clientY, s.app.id);
      const next: DragState = { ...s, x: ev.clientX, y: ev.clientY, overStatus: status, dropIndex: idx };
      dragRef.current = next;
      if (Math.hypot(ev.clientX - s.startX, ev.clientY - s.startY) > CLICK_THRESHOLD) {
        setDragRender({ ...next });
      }

      const scroller = scrollerRef.current;
      if (scroller) {
        const r = scroller.getBoundingClientRect();
        const leftDist = ev.clientX - r.left;
        const rightDist = r.right - ev.clientX;
        if (leftDist < SCROLL_ZONE) {
          scrollDeltaRef.current = -(1 - leftDist / SCROLL_ZONE) * SCROLL_SPEED_MAX;
          if (!scrollRafRef.current) scrollRafRef.current = requestAnimationFrame(tick);
        } else if (rightDist < SCROLL_ZONE) {
          scrollDeltaRef.current = (1 - rightDist / SCROLL_ZONE) * SCROLL_SPEED_MAX;
          if (!scrollRafRef.current) scrollRafRef.current = requestAnimationFrame(tick);
        } else {
          scrollDeltaRef.current = 0;
        }
      }
    }

    function onUp(ev: PointerEvent) {
      dragCleanupRef.current = null;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      cancelAnimationFrame(scrollRafRef.current);
      scrollRafRef.current = 0;
      scrollDeltaRef.current = 0;
      const s = dragRef.current;
      dragRef.current = null;
      setDragRender(null);
      if (!s) return;

      const didMove = Math.hypot(ev.clientX - s.startX, ev.clientY - s.startY) > CLICK_THRESHOLD;
      if (!didMove) { setSelectedApp(s.app); return; }
      if (!s.overStatus) return;

      const { startStatus: ss, overStatus, dropIndex } = s;
      const orderSnapshot = orderRef.current;

      if (overStatus === ss) {
        snapshot();
        applyOrder((prev) => {
          const col = (prev[ss] ?? []).filter((id) => id !== s.app.id);
          col.splice(dropIndex, 0, s.app.id);
          const next = { ...prev, [ss]: col };
          persistOrder(jobId, next);
          return next;
        });
      } else if (DROPPABLE_STATUSES.has(overStatus)) {
        const optimistic: CompanyApplicationRead = { ...s.app, status: overStatus };
        setApplications((prev) => (prev ? prev.map((a) => (a.id === s.app.id ? optimistic : a)) : prev));
        snapshot(s.app.id);
        applyOrder((prev) => {
          const src = (prev[ss] ?? []).filter((id) => id !== s.app.id);
          const dst = [...(prev[overStatus] ?? [])];
          dst.splice(dropIndex, 0, s.app.id);
          const next = { ...prev, [ss]: src, [overStatus]: dst };
          persistOrder(jobId, next);
          return next;
        });
        updateApplicationStatus(jobId, s.app.id, overStatus)
          .then((updated) => {
            setApplications((prev) => (prev ? prev.map((a) => (a.id === s.app.id ? updated : a)) : prev));
          })
          .catch(() => {
            setApplications((prev) => (prev ? prev.map((a) => (a.id === s.app.id ? s.app : a)) : prev));
            snapshot(s.app.id);
            applyOrder(() => { persistOrder(jobId, orderSnapshot); return orderSnapshot; });
          });
      }
    }

    dragCleanupRef.current = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      cancelAnimationFrame(scrollRafRef.current);
      scrollRafRef.current = 0;
      scrollDeltaRef.current = 0;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerup", onUp);
  }

  if (error) {
    return <p className="py-10 text-center text-sm text-danger">{t("company:jobs.kanban.loadError")}</p>;
  }

  if (applications === null) {
    return (
      <div className="overflow-x-auto">
        <div className="grid grid-cols-3 gap-4 min-w-[50rem]">
          {COLUMNS.map((col) => (
            <div key={col.status} className="flex flex-col rounded-xl border border-white/6">
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
    COLUMNS.map(({ status }) => {
      const ids = order[status] ?? [];
      const appMap = new Map(applications.map((a) => [a.id, a]));
      return [status, ids.map((id) => appMap.get(id)).filter(Boolean) as CompanyApplicationRead[]];
    }),
  );

  const draggingId = dragRender?.app.id ?? null;

  return (
    <>
      <p className="mb-3 text-xs text-white/30">
        {t("company:jobs.kanban.totalCandidates", { count: applications.length })}
      </p>

      <div className="overflow-x-auto" ref={scrollerRef}>
        <div className={`grid grid-cols-3 gap-4 min-w-[50rem] ${isDragging ? "cursor-grabbing" : ""}`}>
        {COLUMNS.map((col) => {
          const cards = byStatus[col.status] ?? [];
          const isOver = dragRender?.overStatus === col.status;
          const isDraggingFromHere = dragRender?.startStatus === col.status;
          const dropIdx = isOver ? (dragRender?.dropIndex ?? null) : null;
          const canDrop = isDraggingFromHere || col.droppable;
          const dropLineCls = canDrop ? "bg-success" : "bg-danger";

          return (
            <div
              key={col.status}
              ref={(el) => { colRefs.current[col.status] = el ?? undefined; }}
              data-col={col.status}
              className={`flex flex-col rounded-xl border transition-all duration-150 ${
                isOver
                  ? canDrop
                    ? `border-white/20 ring-1 ${col.dropRingCls} shadow-lg`
                    : "border-danger/40 ring-1 ring-danger/30"
                  : "border-white/6"
              }`}
            >
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
                  className={`min-w-5 rounded-full px-1.5 py-px text-center text-[11px] font-bold tabular-nums ${
                    cards.length > 0 ? `${col.headerBg} ${col.textCls}` : "text-white/20"
                  }`}
                >
                  {cards.length}
                </span>
              </div>

              <div className={`flex flex-1 flex-col gap-2 rounded-b-xl p-3 min-h-40 ${col.colBg}`}>
                {cards.map((app, i) => {
                  const isLifted = app.id === draggingId && isDraggingFromHere;
                  return (
                    <div key={app.id}>
                      {dropIdx === i && isOver && (
                        <div className={`mb-2 h-1 rounded-full ${dropLineCls}`} />
                      )}
                      <div
                        ref={(el) => {
                          if (el) cardElsRef.current.set(app.id, el);
                          else cardElsRef.current.delete(app.id);
                        }}
                        data-card-id={app.id}
                        onPointerDown={(e) => handlePointerDown(e, app)}
                        style={{ touchAction: "none" }}
                        className={`transition-opacity duration-100 ${
                          isLifted ? "opacity-0 pointer-events-none" : "cursor-grab"
                        }`}
                      >
                        <Card app={app} />
                      </div>
                    </div>
                  );
                })}

                {dropIdx === cards.filter((a) => a.id !== draggingId).length && isOver && (
                  <div className={`h-1 rounded-full ${dropLineCls}`} />
                )}

                {cards.length === 0 && !isDragging && (
                  <div className="flex flex-1 items-center justify-center py-8">
                    <span className="text-[11px] text-white/15">—</span>
                  </div>
                )}

                {col.droppable && isDragging && cards.filter((a) => a.id !== draggingId).length === 0 && (
                  <div
                    className={`flex-1 rounded-lg border-2 border-dashed py-6 text-center text-[11px] transition-colors ${
                      isOver ? `border-current ${col.textCls} bg-white/3` : "border-white/10 text-white/20"
                    }`}
                  >
                    {isOver ? t("company:jobs.kanban.dropHere") : ""}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        </div>
      </div>

      {dragRender &&
        createPortal(
          <div
            style={{
              position: "fixed",
              left: dragRender.x - dragRender.offsetX,
              top: dragRender.y - dragRender.offsetY,
              width: dragRender.cardWidth,
              pointerEvents: "none",
              zIndex: 9999,
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
