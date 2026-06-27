import { useCallback, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SortableColumnHeader from "@/components/admin/SortableColumnHeader";
import SortControl from "@/components/admin/SortControl";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import NoResults from "@/components/ui/NoResults";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useColumnSort } from "@/hooks/useColumnSort";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useToast } from "@/hooks/useToast";
import {
  deleteCompany,
  deleteOrphanCompany,
  getActiveCompanies,
} from "@/services/adminCompanies";
import type { CompanyProfileRead } from "@/types/auth";
import type { ActiveCompanyRead } from "@/types/companies";
import { formatDate } from "@/utils/formatDate";

import EditCompanyDialog from "./EditCompanyDialog";

interface ActiveTabProps {
  query: string;
  selectedId: number | null;
  onSelect: (id: number) => void;
  /** Increment to force a full list reload (e.g. after record-pane edit/delete). */
  reloadKey?: number;
  /** Compact rail layout: always render the card list, never the wide table. */
  compact?: boolean;
}

export default function CompanyActiveTab({
  query,
  selectedId,
  onSelect,
  reloadKey = 0,
  compact = false,
}: ActiveTabProps) {
  const { t } = useTranslation(["admin", "md"]);
  const toast = useToast();
  const navigate = useNavigate();

  const { sort, order, toggle } = useColumnSort<"name" | "created_at">({
    column: "created_at",
    order: "desc",
  });
  const handleSort = (column: "name" | "created_at") =>
    toggle(column, column === "name" ? "asc" : "desc");

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ActiveCompanyRead>> =>
      getActiveCompanies({ cursor, sort, order }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sort, order, reloadKey],
  );

  const {
    items: companies,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    updateItem,
    removeItem,
  } = useInfiniteList<ActiveCompanyRead>(fetcher);

  const filteredCompanies = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return companies;
    return companies.filter((row) => {
      const p = row.company_profile;
      const u = row.user;
      return [
        p.name,
        p.contact_first_name,
        p.contact_last_name,
        p.contact_mobile_phone,
        p.contact_landline_phone ?? "",
        u?.email ?? "",
      ].some((s) => s.toLowerCase().includes(q));
    });
  }, [companies, query]);

  const [editing, setEditing] = useState<CompanyProfileRead | null>(null);
  const [deletePending, setDeletePending] = useState<ActiveCompanyRead | null>(null);
  const [isPendingMutation, setIsPendingMutation] = useState(false);

  async function handleDelete() {
    if (!deletePending) return;
    setIsPendingMutation(true);
    try {
      if (deletePending.user) {
        await deleteCompany(deletePending.user.id);
      } else {
        await deleteOrphanCompany(deletePending.company_profile.id);
      }
      const deletedId = deletePending.company_profile.id;
      removeItem((c) => c.company_profile.id === deletedId);
      toast.success(t("admin:companies.deletedToast"));
      setDeletePending(null);
      if (selectedId === deletedId) {
        navigate("/admin/companies");
      }
    } catch {
      toast.error(t("admin:companies.active.deleteError"));
    } finally {
      setIsPendingMutation(false);
    }
  }

  const mobileOnly = compact ? "" : "md:hidden";
  const tableOnly = compact ? "hidden" : "hidden md:block";

  return (
    <>
      {isLoading ? (
        <>
          <div className={mobileOnly}>
            <MobileListSkeleton rows={5} />
          </div>
          <div className={tableOnly}>
            <TableSkeleton rows={5} columns={3} />
          </div>
        </>
      ) : error ? (
        <ErrorState message={t("admin:companies.active.loadError")} onRetry={reload} />
      ) : companies.length === 0 ? (
        <EmptyState
          eyebrow={t("admin:companies.tabs.active")}
          headline={t("admin:companies.active.empty")}
        />
      ) : filteredCompanies.length === 0 ? (
        <NoResults />
      ) : (
        <>
          <div className={`mb-3 ${mobileOnly}`}>
            <SortControl
              ariaLabel={t("admin:companies.active.sort.label")}
              value={`${sort}:${order}`}
              onChange={(col, ord) => toggle(col as "name" | "created_at", ord)}
              options={[
                {
                  value: "created_at:desc",
                  label: t("admin:companies.active.sort.dateDesc"),
                },
                {
                  value: "created_at:asc",
                  label: t("admin:companies.active.sort.dateAsc"),
                },
                { value: "name:asc", label: t("admin:companies.active.sort.nameAsc") },
                { value: "name:desc", label: t("admin:companies.active.sort.nameDesc") },
              ]}
            />
          </div>

          {/* Card list — tap row to navigate to record pane. Always shown in
              compact (rail) mode; mobile-only otherwise. */}
          <div className={`space-y-2 ${mobileOnly}`}>
            {filteredCompanies.map((row) => {
              const isSelected = selectedId === row.company_profile.id;
              return (
                <div
                  key={row.company_profile.id}
                  className={`relative overflow-hidden rounded-xl border bg-card transition-colors duration-200 ${
                    isSelected
                      ? "border-copper/40 bg-card-raised"
                      : "border-white/8 hover:border-white/15"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => onSelect(row.company_profile.id)}
                    className="flex w-full items-center gap-3 px-3 py-3 pe-12 text-start"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-white/90">
                        {row.company_profile.name}
                      </p>
                      <p className="text-xs text-white/40">
                        {row.company_profile.contact_email}
                      </p>
                    </div>
                  </button>
                  <div className="absolute end-1 top-2">
                    <DropdownMenu
                      ariaLabel={t("admin:companies.rowActionsLabel")}
                      trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
                    >
                      <DropdownMenuItem onSelect={() => setEditing(row.company_profile)}>
                        {t("admin:companies.editAction")}
                      </DropdownMenuItem>
                      {row.user?.email && (
                        <DropdownMenuItem
                          onSelect={() => {
                            const email = row.user?.email;
                            if (email) window.open(`mailto:${email}`, "_self");
                          }}
                        >
                          {t("admin:companies.emailAction")}
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        variant="danger"
                        onSelect={() => setDeletePending(row)}
                      >
                        {t("admin:companies.deleteAction")}
                      </DropdownMenuItem>
                    </DropdownMenu>
                  </div>
                </div>
              );
            })}
          </div>

          <div className={`${tableOnly} overflow-x-auto rounded-xl border border-white/8 bg-card`}>
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th
                    className="px-4 py-3 text-start"
                    aria-sort={
                      sort === "name"
                        ? order === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                  >
                    <SortableColumnHeader
                      label={t("admin:companies.active.table.company")}
                      active={sort === "name"}
                      order={order}
                      onClick={() => handleSort("name")}
                    />
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin:companies.active.table.contact")}
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
                      label={t("admin:companies.active.table.joined")}
                      active={sort === "created_at"}
                      order={order}
                      onClick={() => handleSort("created_at")}
                    />
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {filteredCompanies.map((row) => (
                  <tr
                    key={row.company_profile.id}
                    onClick={() => onSelect(row.company_profile.id)}
                    className={`cursor-pointer transition-[background-color] ${
                      selectedId === row.company_profile.id
                        ? "bg-copper/8"
                        : "hover:bg-white/3"
                    }`}
                  >
                    <td className="px-4 py-3">
                      <span className="font-medium text-white/90">
                        {row.company_profile.name}
                      </span>
                      <p className="text-xs text-white/40">
                        {row.company_profile.contact_email}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-white/60">
                      {row.company_profile.contact_first_name}{" "}
                      {row.company_profile.contact_last_name}
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(
                        row.user?.created_at ?? row.company_profile.created_at,
                      )}
                    </td>
                    <td
                      className="px-4 py-3 text-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DropdownMenu
                        ariaLabel={t("admin:companies.rowActionsLabel")}
                        trigger={<KebabButton size="sm" />}
                      >
                        <DropdownMenuItem
                          onSelect={() => onSelect(row.company_profile.id)}
                        >
                          {t("admin:companies.viewAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() => setEditing(row.company_profile)}
                        >
                          {t("admin:companies.editAction")}
                        </DropdownMenuItem>
                        {row.user?.email && (
                          <DropdownMenuItem
                            onSelect={() => {
                              const email = row.user?.email;
                              if (email) window.open(`mailto:${email}`, "_self");
                            }}
                          >
                            {t("admin:companies.emailAction")}
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="danger"
                          onSelect={() => setDeletePending(row)}
                        >
                          {t("admin:companies.deleteAction")}
                        </DropdownMenuItem>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <InfiniteScrollFooter
            sentinelRef={sentinelRef}
            isFetchingMore={isFetchingMore}
          />
        </>
      )}

      <EditCompanyDialog
        profile={editing}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          updateItem(
            (c) => c.company_profile.id === updated.id,
            (() => {
              const target = companies.find((c) => c.company_profile.id === updated.id);
              return {
                user: target?.user ?? null,
                company_profile: updated,
              } as ActiveCompanyRead;
            })(),
          );
          toast.success(t("admin:companies.savedToast"));
          setEditing(null);
        }}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin:companies.deleteConfirmTitle", {
          name: deletePending?.company_profile.name ?? "",
        })}
        message={t("admin:companies.active.deleteConfirm")}
        confirmLabel={t("admin:companies.deleteAction")}
        variant="danger"
        isPending={isPendingMutation}
        onConfirm={handleDelete}
      />
    </>
  );
}
