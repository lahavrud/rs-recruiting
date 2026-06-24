import { useTranslation } from "react-i18next";

import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
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

  return (
    <>
      <div className="space-y-2">
        {candidates.map((c) => {
          const selected = c.id === selectedId;
          return (
            <div
              key={c.id}
              onClick={() => onView(c)}
              aria-selected={selected}
              className={`relative flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 pe-12 transition active:scale-[0.99] ${
                selected
                  ? "border-copper/40 bg-card-raised"
                  : "border-white/8 bg-card hover:border-white/15"
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-white/85">{c.full_name}</p>
                <p className="truncate text-xs text-white/40">{c.email}</p>
              </div>
              <span className="shrink-0 text-[11px] text-white/40">
                {formatDate(c.created_at)}
              </span>
              <div className="absolute end-1 top-2">
                <DropdownMenu
                  ariaLabel={t("admin:candidates.rowActionsLabel")}
                  trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
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
              </div>
            </div>
          );
        })}
      </div>

      <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
    </>
  );
}
