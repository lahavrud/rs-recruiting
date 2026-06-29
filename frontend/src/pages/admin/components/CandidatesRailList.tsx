import { useTranslation } from "react-i18next";

import RailRow from "@/components/admin/RailRow";
import ScoreBadge from "@/components/admin/ScoreBadge";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import { useScrollSelectedIntoView } from "@/hooks/useScrollSelectedIntoView";
import type { CandidateAdminRead } from "@/types/candidates";
import { formatDate } from "@/utils/formatDate";

interface CandidatesRailListProps {
  candidates: CandidateAdminRead[];
  selectedId?: number | null;
  showScore?: boolean;
  onView: (c: CandidateAdminRead) => void;
  onDelete: (c: CandidateAdminRead) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

/** Compact rail list — a row per candidate, used for the 360px master list at every breakpoint. */
export default function CandidatesRailList({
  candidates,
  selectedId,
  showScore = false,
  onView,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: CandidatesRailListProps) {
  const { t } = useTranslation("admin");
  const rowRef = useScrollSelectedIntoView(selectedId, candidates);

  return (
    <>
      <div className="space-y-2">
        {candidates.map((c) => (
          <RailRow
            key={c.id}
            rowRef={rowRef(c.id)}
            selected={c.id === selectedId}
            onClick={() => onView(c)}
            actions={
              <DropdownMenu
                ariaLabel={t("admin:candidates.rowActionsLabel")}
                trigger={<KebabButton />}
              >
                <DropdownMenuItem onSelect={() => onView(c)}>
                  {t("admin:candidates.viewAction")}
                </DropdownMenuItem>
                {!c.is_deleted && (
                  <DropdownMenuItem
                    onSelect={() =>
                      window.open(
                        `mailto:${c.email}?subject=${encodeURIComponent(
                          t("admin:candidates.emailSubject", { name: c.full_name }),
                        )}`,
                        "_self",
                      )
                    }
                  >
                    {t("admin:candidates.emailAction")}
                  </DropdownMenuItem>
                )}
                {!c.is_deleted && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem variant="danger" onSelect={() => onDelete(c)}>
                      {t("admin:candidates.deleteAction")}
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenu>
            }
          >
            <div className={`min-w-0 flex-1 ${c.is_deleted ? "opacity-50" : ""}`}>
              <div className="flex items-center gap-2">
                <p className="truncate font-medium text-white/85">{c.full_name}</p>
                {c.is_deleted && (
                  <span className="shrink-0 rounded bg-danger/15 px-1 py-0.5 text-[9px] font-medium text-danger/70">
                    {t("admin:candidates.statusDeleted")}
                  </span>
                )}
                {showScore && c.ai_score != null && <ScoreBadge score={c.ai_score} />}
              </div>
              {c.resume_summary ? (
                <p className="truncate text-xs text-white/45">{c.resume_summary}</p>
              ) : (
                <p className="truncate text-xs text-white/40">{c.email}</p>
              )}
            </div>
            <span className="shrink-0 text-[11px] text-white/40">
              {formatDate(c.created_at)}
            </span>
          </RailRow>
        ))}
      </div>

      <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
    </>
  );
}
