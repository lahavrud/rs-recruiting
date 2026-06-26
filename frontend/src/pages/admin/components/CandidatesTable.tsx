import { useTranslation } from "react-i18next";

import ScoreBadge from "@/components/admin/ScoreBadge";
import SortableColumnHeader from "@/components/admin/SortableColumnHeader";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import ResumeButton from "@/components/ui/ResumeViewer";
import type { SortOrder } from "@/hooks/useColumnSort";
import type { CandidateProfileRead } from "@/types/candidates";
import { formatDate } from "@/utils/formatDate";
import { sanitizeLinkedInUrl } from "@/utils/validators";

interface CandidatesTableProps {
  candidates: CandidateProfileRead[];
  sort: "name" | "created_at";
  order: SortOrder;
  showScore?: boolean;
  onSort: (column: "name" | "created_at") => void;
  onView: (c: CandidateProfileRead) => void;
  onDelete: (c: CandidateProfileRead) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

export default function CandidatesTable({
  candidates,
  sort,
  order,
  showScore = false,
  onSort,
  onView,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: CandidatesTableProps) {
  const { t } = useTranslation("admin");

  return (
    <>
      <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
        <table className="min-w-full divide-y divide-white/6 text-sm">
          <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
            <tr>
              <th
                className="px-4 py-3 text-start"
                aria-sort={
                  sort === "name" ? (order === "asc" ? "ascending" : "descending") : undefined
                }
              >
                <SortableColumnHeader
                  label={t("admin:candidates.table.name")}
                  active={sort === "name"}
                  order={order}
                  onClick={() => onSort("name")}
                />
              </th>
              <th className="px-4 py-3 text-start">
                {t("admin:candidates.table.phone")}
              </th>
              <th className="px-4 py-3 text-start">
                {t("admin:candidates.table.resume")}
              </th>
              <th className="px-4 py-3 text-start">
                {t("admin:candidates.table.linkedin")}
              </th>
              <th
                className="px-4 py-3 text-start"
                aria-sort={
                  sort === "created_at"
                    ? order === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
              >
                <SortableColumnHeader
                  label={t("admin:candidates.table.date")}
                  active={sort === "created_at"}
                  order={order}
                  onClick={() => onSort("created_at")}
                />
              </th>
              <th className="px-4 py-3 text-end" aria-hidden />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/6">
            {candidates.map((c) => (
              <tr
                key={c.id}
                onClick={() => onView(c)}
                className="cursor-pointer transition-[background-color] hover:bg-white/3"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-white/85">{c.full_name}</p>
                    {showScore && c.ai_score != null && <ScoreBadge score={c.ai_score} />}
                  </div>
                  <p className="text-xs text-white/40">{c.email}</p>
                </td>
                <td className="px-4 py-3 text-white/60">
                  {c.phone ?? <span className="text-white/20">—</span>}
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  {c.resume_path ? (
                    <ResumeButton
                      resumePath={c.resume_path}
                      candidateName={c.full_name}
                      label={t("admin:candidates.table.resume")}
                    />
                  ) : (
                    <span className="text-white/20">
                      {t("admin:candidates.noFile")}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  {c.linkedin_url ? (
                    <a
                      href={sanitizeLinkedInUrl(c.linkedin_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-copper hover:text-gold"
                    >
                      LinkedIn ↗
                    </a>
                  ) : (
                    <span className="text-white/20">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-white/40">{formatDate(c.created_at)}</td>
                <td className="px-4 py-3 text-end" onClick={(e) => e.stopPropagation()}>
                  <DropdownMenu
                    ariaLabel={t("admin:candidates.rowActionsLabel")}
                    trigger={<KebabButton size="sm" />}
                  >
                    <DropdownMenuItem onSelect={() => onView(c)}>
                      {t("admin:candidates.viewAction")}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem variant="danger" onSelect={() => onDelete(c)}>
                      {t("admin:candidates.deleteAction")}
                    </DropdownMenuItem>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
    </>
  );
}
