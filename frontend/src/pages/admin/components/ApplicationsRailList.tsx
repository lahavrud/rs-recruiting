import { useEffect, useRef } from "react";

import { useTranslation } from "react-i18next";

import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import StatusBadge from "@/components/ui/StatusBadge";
import type { ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

interface ApplicationsRailListProps {
  applications: ApplicationWithDetails[];
  selectedId?: number | null;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  onView: (app: ApplicationWithDetails) => void;
  onUpdateStatus: (app: ApplicationWithDetails) => void;
  onEditNotes: (app: ApplicationWithDetails) => void;
  onDelete: (app: ApplicationWithDetails) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

/** Compact rail list — a row per application, used for the 360px master list at every breakpoint. */
export default function ApplicationsRailList({
  applications,
  selectedId,
  statusLabels,
  statusColors,
  onView,
  onUpdateStatus,
  onEditNotes,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: ApplicationsRailListProps) {
  const { t } = useTranslation("admin");
  const rowRefs = useRef(new Map<number, HTMLDivElement>());

  useEffect(() => {
    if (selectedId == null) return;
    rowRefs.current.get(selectedId)?.scrollIntoView({ block: "nearest" });
  }, [selectedId, applications]);

  return (
    <>
      <div className="space-y-2">
        {applications.map((app) => {
          const selected = app.id === selectedId;
          return (
            <div
              key={app.id}
              ref={(node) => {
                if (node) rowRefs.current.set(app.id, node);
                else rowRefs.current.delete(app.id);
              }}
              onClick={() => onView(app)}
              aria-selected={selected}
              className={`relative flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 pe-12 transition active:scale-[0.99] ${
                selected
                  ? "border-copper/40 bg-card-raised"
                  : "border-white/8 bg-card hover:border-white/15"
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-white/85">
                  {app.candidate.full_name}
                </p>
                <p className="truncate text-xs text-white/40">{app.job.title}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <StatusBadge
                  label={statusLabels[app.status]}
                  colorCls={statusColors[app.status]}
                />
                <span className="text-[11px] text-white/40">
                  {formatDate(app.created_at)}
                </span>
              </div>
              <div className="absolute end-1 top-2">
                <DropdownMenu
                  ariaLabel={t("admin:applications.rowActionsLabel")}
                  trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
                >
                  <DropdownMenuItem onSelect={() => onView(app)}>
                    {t("admin:applications.viewAction")}
                  </DropdownMenuItem>
                  {app.status !== ApplicationStatus.WITHDRAWN && (
                    <DropdownMenuItem onSelect={() => onUpdateStatus(app)}>
                      {t("admin:applications.updateStatusAction")}
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onSelect={() => onEditNotes(app)}>
                    {t("admin:applications.editNotesAction")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="danger" onSelect={() => onDelete(app)}>
                    {t("admin:applications.deleteAction")}
                  </DropdownMenuItem>
                </DropdownMenu>
              </div>
            </div>
          );
        })}
      </div>

      <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
    </>
  );
}
