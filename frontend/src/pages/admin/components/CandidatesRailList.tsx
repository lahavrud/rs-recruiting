import { useTranslation } from "react-i18next";

import RailRow from "@/components/admin/RailRow";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import { useScrollSelectedIntoView } from "@/hooks/useScrollSelectedIntoView";
import type { CandidateProfileRead } from "@/types/candidates";
import { formatDate } from "@/utils/formatDate";

interface CandidatesRailListProps {
  candidates: CandidateProfileRead[];
  selectedId?: number | null;
  onView: (c: CandidateProfileRead) => void;
  onDelete: (c: CandidateProfileRead) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

/** Compact rail list — a row per candidate, used for the 360px master list at every breakpoint. */
export default function CandidatesRailList({
  candidates,
  selectedId,
  onView,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: CandidatesRailListProps) {
  const { t } = useTranslation('admin');
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
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="danger" onSelect={() => onDelete(c)}>
                  {t("admin:candidates.deleteAction")}
                </DropdownMenuItem>
              </DropdownMenu>
            }
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white/85">{c.full_name}</p>
              <p className="truncate text-xs text-white/40">{c.email}</p>
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
