import { type DragEvent, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import CandidateDetailDrawer from "@/pages/company/components/CandidateDetailDrawer";
import { getJobApplications, updateApplicationStatus } from "@/services/companyJobs";
import type { CompanyApplicationRead } from "@/types/companies";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

// ─── Column config ────────────────────────────────────────────────────────────

interface ColumnDef {
  status: string;
  labelKey: string;
  accent: string;       // border + text
  headerBg: string;     // column header bg
  columnBg: string;     // column body bg
  dotCls: string;       // status dot
}

const COLUMNS: ColumnDef[] = [
  {
    status: ApplicationStatus.NEW,
    labelKey: "company:jobs.kanban.columns.NEW",
    accent: "text-info border-info/25",
    headerBg: "bg-info/10",
    columnBg: "bg-info/3",
    dotCls: "bg-info",
  },
  {
    status: ApplicationStatus.APPROVED_BY_ADMIN,
    labelKey: "company:jobs.kanban.columns.APPROVED_BY_ADMIN",
    accent: "text-copper border-copper/25",
    headerBg: "bg-copper/10",
    columnBg: "bg-copper/3",
    dotCls: "bg-copper",
  },
  {
    status: ApplicationStatus.HIRED,
    labelKey: "company:jobs.kanban.columns.HIRED",
    accent: "text-hired border-hired/25",
    headerBg: "bg-hired/10",
    columnBg: "bg-hired/3",
    dotCls: "bg-hired",
  },
  {
    status: ApplicationStatus.REJECTED,
    labelKey: "company:jobs.kanban.columns.REJECTED",
    accent: "text-danger border-danger/25",
    headerBg: "bg-danger/10",
    columnBg: "bg-danger/3",
    dotCls: "bg-danger",
  },
  {
    status: ApplicationStatus.WITHDRAWN,
    labelKey: "company:jobs.kanban.columns.WITHDRAWN",
    accent: "text-white/35 border-white/10",
    headerBg: "bg-white/5",
    columnBg: "bg-white/2",
    dotCls: "bg-white/30",
  },
];

const COMPANY_DROP_TARGETS = new Set<string>([
  ApplicationStatus.HIRED,
  ApplicationStatus.REJECTED,
]);

const PCT_MULTIPLIER = 100;
const SCORE_HIGH = 80;
const SCORE_MID = 65;
const COLUMN_WIDTH_PX = 240;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();
}

const AVATAR_COLORS = [
  "bg-copper/20 text-copper",
  "bg-info/20 text-info",
  "bg-hired/20 text-hired",
  "bg-warning/20 text-warning",
  "bg-nickel/20 text-nickel",
];

function avatarColor(id: number): string {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

// ─── ScoreBar ─────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * PCT_MULTIPLIER);
  const colorCls =
    pct >= SCORE_HIGH ? "bg-success" : pct >= SCORE_MID ? "bg-copper" : "bg-warning";
  return (
    <div className="flex items-center gap-2 pt-0.5">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorCls}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 text-[10px] tabular-nums text-white/40">{pct}%</span>
    </div>
  );
}

// ─── CandidateCard ────────────────────────────────────────────────────────────

interface CandidateCardProps {
  app: CompanyApplicationRead;
  onClick: () => void;
  onDragStart: (e: DragEvent<HTMLDivElement>) => void;
  isDragging: boolean;
}

function CandidateCard({ app, onClick, onDragStart, isDragging }: CandidateCardProps) {
  const { t } = useTranslation("company");
  const initials = getInitials(app.candidate.full_name);
  const avColor = avatarColor(app.candidate.id);

  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      onDragStart={onDragStart}
      className={`group cursor-pointer select-none rounded-xl border border-white/6 bg-card p-3.5 space-y-2.5 shadow-sm transition-all duration-150
        hover:border-white/15 hover:bg-card-raised hover:shadow-md hover:-translate-y-px
        active:scale-[0.98] active:shadow-none
        ${isDragging ? "opacity-40 scale-[0.98]" : "opacity-100"}`}
    >
      {/* Avatar + name row */}
      <div className="flex items-center gap-2.5">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${avColor}`}
        >
          {initials}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold leading-snug text-white/90">
            {app.candidate.full_name}
          </p>
          <p className="truncate text-[11px] text-white/40">{app.candidate.email}</p>
        </div>
      </div>

      {/* Match score */}
      {app.match_score != null && <ScoreBar score={app.match_score} />}

      {/* AI review */}
      {app.ai_review ? (
        <p className="line-clamp-2 text-[11px] leading-relaxed text-white/50 italic">
          {app.ai_review}
        </p>
      ) : null}

      {/* Footer */}
      <div className="flex items-center justify-between pt-0.5">
        <p className="text-[10px] text-white/25">
          {t("company:jobs.kanban.appliedOn")}
          {formatDate(app.created_at)}
        </p>
        <span className="text-[10px] text-white/20 opacity-0 transition group-hover:opacity-100">
          {t("company:jobs.kanban.clickToView")}
        </span>
      </div>
    </div>
  );
}

// ─── KanbanColumn ─────────────────────────────────────────────────────────────

interface KanbanColumnProps {
  col: ColumnDef;
  cards: CompanyApplicationRead[];
  isDragOver: boolean;
  isDraggingAny: boolean;
  selectedId: number | null;
  onCardClick: (app: CompanyApplicationRead) => void;
  onCardDragStart: (e: DragEvent<HTMLDivElement>, id: number) => void;
  onDragOver: (e: DragEvent<HTMLDivElement>) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent<HTMLDivElement>) => void;
  draggingId: number | null;
}

function KanbanColumn({
  col,
  cards,
  isDragOver,
  isDraggingAny,
  onCardClick,
  onCardDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
  draggingId,
}: KanbanColumnProps) {
  const { t } = useTranslation("company");
  const isDropTarget = COMPANY_DROP_TARGETS.has(col.status);
  const showDropZone = isDropTarget && isDraggingAny;

  return (
    <div
      className={`flex shrink-0 flex-col gap-0 rounded-xl border transition-all duration-200
        ${isDragOver ? "border-copper/40 shadow-lg shadow-copper/5" : "border-white/6"}
      `}
      style={{ width: `${COLUMN_WIDTH_PX}px` }}
      onDragOver={isDropTarget ? onDragOver : undefined}
      onDragLeave={isDropTarget ? onDragLeave : undefined}
      onDrop={isDropTarget ? onDrop : undefined}
    >
      {/* Column header */}
      <div
        className={`flex items-center justify-between rounded-t-xl border-b border-white/6 px-4 py-3 ${col.headerBg}`}
      >
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${col.dotCls}`} />
          <span className={`text-[11px] font-semibold uppercase tracking-widest ${col.accent.split(" ")[0]}`}>
            {t(col.labelKey)}
          </span>
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums
            ${cards.length > 0 ? `${col.headerBg} ${col.accent.split(" ")[0]}` : "text-white/20"}`}
        >
          {cards.length}
        </span>
      </div>

      {/* Column body */}
      <div
        className={`flex flex-1 flex-col gap-2 rounded-b-xl p-3 min-h-32
          ${col.columnBg}
          ${isDragOver ? "ring-1 ring-inset ring-copper/25" : ""}
        `}
      >
        {cards.map((app) => (
          <CandidateCard
            key={app.id}
            app={app}
            onClick={() => onCardClick(app)}
            onDragStart={(e) => onCardDragStart(e, app.id)}
            isDragging={draggingId === app.id}
          />
        ))}

        {/* Drop zone hint */}
        {showDropZone && cards.length === 0 && (
          <div
            className={`flex flex-1 items-center justify-center rounded-lg border-2 border-dashed py-6 text-center text-[11px] transition-colors
              ${isDragOver ? "border-copper/40 text-copper/60 bg-copper/5" : "border-white/8 text-white/20"}`}
          >
            {t("company:jobs.kanban.dropHere")}
          </div>
        )}

        {/* Empty column (not drag target) */}
        {!showDropZone && cards.length === 0 && (
          <div className="flex flex-1 items-center justify-center py-6">
            <span className="text-[11px] text-white/15">—</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── JobKanban ────────────────────────────────────────────────────────────────

interface JobKanbanProps {
  jobId: number;
}

export default function JobKanban({ jobId }: JobKanbanProps) {
  const { t } = useTranslation("company");
  const [applications, setApplications] = useState<CompanyApplicationRead[] | null>(null);
  const [error, setError] = useState(false);
  const [selectedApp, setSelectedApp] = useState<CompanyApplicationRead | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getJobApplications(jobId)
      .then((apps) => {
        if (!cancelled) setApplications(apps);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  function handleDragStart(e: DragEvent<HTMLDivElement>, appId: number) {
    e.dataTransfer.setData("text/plain", String(appId));
    e.dataTransfer.effectAllowed = "move";
    setDraggingId(appId);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>, targetStatus: string) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverStatus(targetStatus);
  }

  function handleDragLeave() {
    setDragOverStatus(null);
  }

  async function handleDrop(e: DragEvent<HTMLDivElement>, targetStatus: string) {
    e.preventDefault();
    setDragOverStatus(null);
    const appId = parseInt(e.dataTransfer.getData("text/plain"), 10);
    setDraggingId(null);
    if (!appId || !applications) return;

    const app = applications.find((a) => a.id === appId);
    if (!app || app.status === targetStatus) return;

    const updated = await updateApplicationStatus(jobId, appId, targetStatus).catch(() => null);
    if (updated) {
      setApplications((prev) =>
        prev ? prev.map((a) => (a.id === appId ? updated : a)) : prev,
      );
      if (selectedApp?.id === appId) setSelectedApp(updated);
    }
  }

  if (error) {
    return (
      <p className="py-10 text-center text-sm text-danger">
        {t("company:jobs.kanban.loadError")}
      </p>
    );
  }

  if (applications === null) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-2">
        {COLUMNS.map((col) => (
          <div
            key={col.status}
            className="flex shrink-0 flex-col rounded-xl border border-white/6"
            style={{ width: `${COLUMN_WIDTH_PX}px` }}
          >
            <div className={`rounded-t-xl border-b border-white/6 px-4 py-3 ${col.headerBg}`}>
              <div className="h-3 w-16 animate-pulse rounded bg-white/10" />
            </div>
            <div className={`space-y-2 rounded-b-xl p-3 min-h-32 ${col.columnBg}`}>
              {[1, 2].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-xl bg-white/4" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  const byStatus = Object.fromEntries(
    COLUMNS.map(({ status }) => [status, applications.filter((a) => a.status === status)]),
  );

  const totalCount = applications.length;

  return (
    <>
      {totalCount === 0 ? (
        <div className="rounded-xl border border-dashed border-white/8 py-16 text-center text-sm text-white/25">
          {t("company:jobs.kanban.empty")}
        </div>
      ) : (
        <div>
          <p className="mb-3 text-xs text-white/30">
            {t("company:jobs.kanban.totalCandidates", { count: totalCount })}
          </p>
          <div
            className="flex gap-3 overflow-x-auto pb-3"
            onDragEnd={() => {
              setDraggingId(null);
              setDragOverStatus(null);
            }}
          >
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.status}
                col={col}
                cards={byStatus[col.status]}
                isDragOver={dragOverStatus === col.status}
                isDraggingAny={draggingId !== null}
                selectedId={selectedApp?.id ?? null}
                onCardClick={setSelectedApp}
                onCardDragStart={handleDragStart}
                onDragOver={(e) => handleDragOver(e, col.status)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, col.status)}
                draggingId={draggingId}
              />
            ))}
          </div>
        </div>
      )}

      <CandidateDetailDrawer app={selectedApp} onClose={() => setSelectedApp(null)} />
    </>
  );
}
