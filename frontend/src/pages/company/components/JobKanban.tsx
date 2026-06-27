import { type DragEvent, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import CandidateDetailDrawer from "@/pages/company/components/CandidateDetailDrawer";
import { getJobApplications, updateApplicationStatus } from "@/services/companyJobs";
import type { CompanyApplicationRead } from "@/types/companies";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

const KANBAN_COLUMNS: { status: string; labelKey: string }[] = [
  { status: ApplicationStatus.NEW, labelKey: "company:jobs.kanban.columns.NEW" },
  {
    status: ApplicationStatus.APPROVED_BY_ADMIN,
    labelKey: "company:jobs.kanban.columns.APPROVED_BY_ADMIN",
  },
  { status: ApplicationStatus.HIRED, labelKey: "company:jobs.kanban.columns.HIRED" },
  { status: ApplicationStatus.REJECTED, labelKey: "company:jobs.kanban.columns.REJECTED" },
  { status: ApplicationStatus.WITHDRAWN, labelKey: "company:jobs.kanban.columns.WITHDRAWN" },
];

const COLUMN_ACCENT: Record<string, string> = {
  [ApplicationStatus.NEW]: "border-info/30 text-info",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "border-copper/30 text-copper",
  [ApplicationStatus.HIRED]: "border-hired/30 text-hired",
  [ApplicationStatus.REJECTED]: "border-danger/30 text-danger",
  [ApplicationStatus.WITHDRAWN]: "border-white/12 text-white/35",
};

const COLUMN_HEADER_BG: Record<string, string> = {
  [ApplicationStatus.NEW]: "bg-info/8",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "bg-copper/8",
  [ApplicationStatus.HIRED]: "bg-hired/8",
  [ApplicationStatus.REJECTED]: "bg-danger/8",
  [ApplicationStatus.WITHDRAWN]: "bg-white/4",
};

const COMPANY_DROP_TARGETS = new Set<string>([
  ApplicationStatus.HIRED,
  ApplicationStatus.REJECTED,
]);

const PCT_MULTIPLIER = 100;
const SCORE_HIGH = 80;
const SCORE_MID = 65;
const COLUMN_MIN_WIDTH_PX = 220;

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * PCT_MULTIPLIER);
  const colorCls = pct >= SCORE_HIGH ? "bg-success" : pct >= SCORE_MID ? "bg-copper" : "bg-warning";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-12 overflow-hidden rounded-full bg-white/8">
        <div className={`h-full rounded-full ${colorCls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] tabular-nums text-white/45">{pct}%</span>
    </div>
  );
}

interface CandidateCardProps {
  app: CompanyApplicationRead;
  onClick: () => void;
  onDragStart: (e: DragEvent<HTMLDivElement>) => void;
}

function CandidateCard({ app, onClick, onDragStart }: CandidateCardProps) {
  const { t } = useTranslation("company");
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      onDragStart={onDragStart}
      className="cursor-pointer rounded-lg border border-white/8 bg-card-raised p-3 space-y-1.5 transition hover:border-copper/30 hover:bg-card-raised/80 active:scale-[0.98]"
    >
      <p className="text-sm font-medium text-white/90">{app.candidate.full_name}</p>

      {app.match_score != null && <ScoreBar score={app.match_score} />}

      {app.ai_review ? (
        <p className="line-clamp-2 text-[11px] leading-relaxed text-white/50">
          {app.ai_review}
        </p>
      ) : null}

      <p className="text-[10px] text-white/25">
        {t("company:jobs.kanban.appliedOn")}
        {formatDate(app.created_at)}
      </p>
    </div>
  );
}

interface DropColumnProps {
  status: string;
  isDropTarget: boolean;
  isDragOver: boolean;
  children: React.ReactNode;
  onDragOver: (e: DragEvent<HTMLDivElement>) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent<HTMLDivElement>) => void;
}

function DropColumn({
  status,
  isDropTarget,
  isDragOver,
  children,
  onDragOver,
  onDragLeave,
  onDrop,
}: DropColumnProps) {
  return (
    <div
      onDragOver={isDropTarget ? onDragOver : undefined}
      onDragLeave={isDropTarget ? onDragLeave : undefined}
      onDrop={isDropTarget ? onDrop : undefined}
      className={`flex-1 rounded-lg transition ${
        isDragOver ? "ring-1 ring-copper/40 bg-copper/5" : ""
      }`}
      data-status={status}
    >
      {children}
    </div>
  );
}

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
      <p className="py-8 text-center text-sm text-danger">
        {t("company:jobs.kanban.loadError")}
      </p>
    );
  }

  if (applications === null) {
    return (
      <p className="py-8 text-center text-sm text-white/30">
        {t("company:jobs.kanban.loading")}
      </p>
    );
  }

  if (applications.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-white/30">
        {t("company:jobs.kanban.empty")}
      </p>
    );
  }

  const byStatus = Object.fromEntries(
    KANBAN_COLUMNS.map(({ status }) => [
      status,
      applications.filter((a) => a.status === status),
    ]),
  );

  const activeColumns = KANBAN_COLUMNS.filter(
    ({ status }) => byStatus[status].length > 0 || COMPANY_DROP_TARGETS.has(status),
  );

  return (
    <>
      <div className="overflow-x-auto">
        <div
          className="flex gap-3 pb-2"
          style={{ minWidth: `${activeColumns.length * COLUMN_MIN_WIDTH_PX}px` }}
          onDragEnd={() => {
            setDraggingId(null);
            setDragOverStatus(null);
          }}
        >
          {activeColumns.map(({ status, labelKey }) => {
            const cards = byStatus[status];
            const accentCls = COLUMN_ACCENT[status] ?? "border-white/12 text-white/35";
            const headerBg = COLUMN_HEADER_BG[status] ?? "bg-white/4";
            const isDropTarget = COMPANY_DROP_TARGETS.has(status);
            const isDragOver = dragOverStatus === status && draggingId !== null;

            return (
              <DropColumn
                key={status}
                status={status}
                isDropTarget={isDropTarget}
                isDragOver={isDragOver}
                onDragOver={(e) => handleDragOver(e, status)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, status)}
              >
                <div className="flex w-52 shrink-0 flex-col gap-2">
                  <div
                    className={`flex items-center justify-between rounded-lg border px-3 py-2 ${accentCls} ${headerBg}`}
                  >
                    <span className="text-[10px] font-semibold uppercase tracking-widest">
                      {t(labelKey)}
                    </span>
                    <span className="rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold">
                      {cards.length}
                    </span>
                  </div>

                  <div className="space-y-2 min-h-12">
                    {cards.map((app) => (
                      <CandidateCard
                        key={app.id}
                        app={app}
                        onClick={() => setSelectedApp(app)}
                        onDragStart={(e) => handleDragStart(e, app.id)}
                      />
                    ))}
                    {isDropTarget && cards.length === 0 && (
                      <div
                        className={`rounded-lg border-2 border-dashed p-4 text-center text-[11px] transition ${
                          isDragOver
                            ? "border-copper/50 text-copper/60"
                            : "border-white/8 text-white/20"
                        }`}
                      >
                        {t("company:jobs.kanban.dropHere")}
                      </div>
                    )}
                  </div>
                </div>
              </DropColumn>
            );
          })}
        </div>
      </div>

      <CandidateDetailDrawer app={selectedApp} onClose={() => setSelectedApp(null)} />
    </>
  );
}
