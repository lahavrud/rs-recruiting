import { useTranslation } from "react-i18next";
import type { CandidateProfileRead } from "@/types/api";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import ResumeButton from "@/components/ui/ResumeViewer";
import { formatDate } from "@/utils/formatDate";
import { sanitizeLinkedInUrl } from "@/utils/validators";

interface CandidatesTableProps {
  candidates: CandidateProfileRead[];
  onView: (c: CandidateProfileRead) => void;
  onEdit: (c: CandidateProfileRead) => void;
  onDelete: (c: CandidateProfileRead) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

export default function CandidatesTable({
  candidates,
  onView,
  onEdit,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: CandidatesTableProps) {
  const { t } = useTranslation('admin');

  return (
    <>
      <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
        <table className="min-w-full divide-y divide-white/6 text-sm">
          <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
            <tr>
              <th className="px-4 py-3 text-start">
                {t("admin:candidates.table.name")}
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
              <th className="px-4 py-3 text-start">
                {t("admin:candidates.table.date")}
              </th>
              <th className="px-4 py-3 text-end" aria-hidden />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/6">
            {candidates.map((c) => (
              <tr
                key={c.id}
                onClick={() => onView(c)}
                className="cursor-pointer transition hover:bg-white/3"
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-white/85">{c.full_name}</p>
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
                <td
                  className="px-4 py-3 text-end"
                  onClick={(e) => e.stopPropagation()}
                >
                  <DropdownMenu
                    ariaLabel={t("admin:candidates.rowActionsLabel")}
                    trigger={<KebabButton size="sm" />}
                  >
                    <DropdownMenuItem onSelect={() => onView(c)}>
                      {t("admin:candidates.viewAction")}
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => onEdit(c)}>
                      {t("admin:candidates.editAction")}
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
