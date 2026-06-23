import { useCallback, useMemo, useRef, useState } from "react";

import { useTranslation } from "react-i18next";

import MobileEntityCard from "@/components/admin/MobileEntityCard";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import Button from "@/components/ui/Button";
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
import StatusBadge from "@/components/ui/StatusBadge";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useToast } from "@/hooks/useToast";
import {
  approveCompany,
  getPendingCompanies,
  rejectCompany,
} from "@/services/adminCompanies";
import type { CompanyProfileRead, PendingCompanyRead } from "@/types/api";
import { formatDate } from "@/utils/formatDate";

import CompanyDetailDialog, { CompanyDetailBody } from "./CompanyDetailDialog";


export default function CompanyPendingTab({ query }: { query: string }) {
  const { t } = useTranslation(['admin', 'md']);
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<PendingCompanyRead>> =>
      getPendingCompanies({ cursor }),
    [],
  );

  const {
    items: companies,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    removeItem,
  } = useInfiniteList<PendingCompanyRead>(fetcher);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return companies;
    return companies.filter((row) => {
      const p = row.company_profile;
      return [
        p.name,
        p.contact_first_name,
        p.contact_last_name,
        p.contact_mobile_phone,
        row.user.email,
      ].some((s) => s.toLowerCase().includes(q));
    });
  }, [companies, query]);

  const [rejectPending, setRejectPending] = useState<PendingCompanyRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);
  const [detail, setDetail] = useState<CompanyProfileRead | null>(null);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  // Optimistic set: IDs approved this session before the list reloads.
  // invitation_sent (from backend) covers the persistent case after refresh.
  const [approvedIds, setApprovedIds] = useState<Set<number>>(new Set());
  const approvingRef = useRef<number | null>(null);

  function isInvitationSent(row: PendingCompanyRead) {
    return row.invitation_sent || approvedIds.has(row.user.id);
  }

  async function handleApprove(row: PendingCompanyRead) {
    if (approvingRef.current !== null) return;
    const alreadySent = isInvitationSent(row);
    approvingRef.current = row.user.id;
    setApprovingId(row.user.id);
    try {
      await approveCompany(row.user.id);
      setApprovedIds((prev) => new Set(prev).add(row.user.id));
      toast.success(
        t(alreadySent ? "admin:companies.resendApprovalToast" : "admin:companies.approvedToast"),
      );
    } catch {
      toast.error(t("admin:companies.approveError"));
    } finally {
      approvingRef.current = null;
      setApprovingId(null);
    }
  }

  async function handleRejectConfirm() {
    if (!rejectPending) return;
    setPendingMutation(true);
    try {
      await rejectCompany(rejectPending.user.id);
      removeItem((c) => c.user.id === rejectPending.user.id);
      toast.success(t("admin:companies.rejectedToast"));
      setRejectPending(null);
    } catch {
      toast.error(t("admin:companies.rejectError"));
    } finally {
      setPendingMutation(false);
    }
  }

  function renderRowActions(row: PendingCompanyRead) {
    return (
      <DropdownMenu
        ariaLabel={t("admin:companies.rowActionsLabel")}
        trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
      >
        <DropdownMenuItem onSelect={() => setDetail(row.company_profile)}>
          {t("admin:companies.viewAction")}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => window.open(`mailto:${row.user.email}`, "_self")}
        >
          {t("admin:companies.emailAction")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="danger" onSelect={() => setRejectPending(row)}>
          {t("admin:companies.rejectAction")}
        </DropdownMenuItem>
      </DropdownMenu>
    );
  }

  return (
    <>
      {isLoading ? (
        <>
          <div className="md:hidden">
            <MobileListSkeleton rows={4} />
          </div>
          <div className="hidden md:block">
            <TableSkeleton rows={4} columns={3} />
          </div>
        </>
      ) : error ? (
        <ErrorState message={t("admin:companies.loadError")} onRetry={reload} />
      ) : companies.length === 0 ? (
        <EmptyState
          eyebrow={t("admin:companies.tabs.pending")}
          headline={t("admin:companies.empty")}
        />
      ) : filtered.length === 0 ? (
        <NoResults />
      ) : (
        <>
          {/* Mobile: collapsible cards with detail body inline */}
          <div className="space-y-2 md:hidden">
            {filtered.map((row) => (
              <MobileEntityCard
                key={row.user.id}
                title={
                  <span className="block truncate font-medium text-white/90">
                    {row.company_profile.name}
                  </span>
                }
                badge={
                  isInvitationSent(row) ? (
                    <StatusBadge
                      label={t("admin:companies.invitationSentBadge")}
                      colorCls="bg-warning/10 text-warning"
                    />
                  ) : undefined
                }
                actions={renderRowActions(row)}
              >
                <CompanyDetailBody profile={row.company_profile} />
                <div className="mt-4 flex gap-2">
                  <Button
                    variant={isInvitationSent(row) ? "ghost" : "success"}
                    onClick={() => handleApprove(row)}
                    disabled={approvingId !== null}
                    className="flex-1"
                  >
                    {approvingId === row.user.id
                      ? t("admin:companies.approvingButton")
                      : isInvitationSent(row)
                        ? t("admin:companies.resendApprovalAction")
                        : t("admin:companies.approveAction")}
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => setRejectPending(row)}
                    disabled={approvingId !== null}
                    className="flex-1"
                  >
                    {t("admin:companies.rejectAction")}
                  </Button>
                </div>
              </MobileEntityCard>
            ))}
          </div>

          {/* Desktop: card rows with inline approve + 3-dot menu */}
          <div className="hidden space-y-3 md:block">
            {filtered.map((row) => (
              <div
                key={row.user.id}
                onClick={() => setDetail(row.company_profile)}
                className="flex cursor-pointer flex-col gap-3 rounded-xl border border-white/8 bg-card p-4 transition hover:bg-card-raised sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium text-white/90">
                      {row.company_profile.name}
                    </span>
                    {isInvitationSent(row) && (
                      <StatusBadge
                        label={t("admin:companies.invitationSentBadge")}
                        colorCls="bg-warning/10 text-warning"
                      />
                    )}
                  </div>
                  <p className="truncate text-xs text-white/45">{row.user.email}</p>
                  <p className="mt-1 text-xs text-white/35">
                    {t("admin:companies.contactLabel")}:{" "}
                    {row.company_profile.contact_first_name}{" "}
                    {row.company_profile.contact_last_name} ·{" "}
                    {t("admin:companies.registeredLabel")}{" "}
                    {formatDate(row.user.created_at)}
                  </p>
                </div>
                <div
                  className="flex shrink-0 items-center gap-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button
                    variant={isInvitationSent(row) ? "ghost" : "success"}
                    size="sm"
                    onClick={() => handleApprove(row)}
                    disabled={approvingId !== null}
                  >
                    {approvingId === row.user.id
                      ? t("admin:companies.approvingButton")
                      : isInvitationSent(row)
                        ? t("admin:companies.resendApprovalAction")
                        : t("admin:companies.approveAction")}
                  </Button>
                  {renderRowActions(row)}
                </div>
              </div>
            ))}
          </div>

          <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
        </>
      )}

      <CompanyDetailDialog
        profile={detail}
        onClose={() => setDetail(null)}
        onEdit={() => setDetail(null)}
        hideEditButton
      />

      <ConfirmDialog
        open={rejectPending != null}
        onOpenChange={(o) => !o && setRejectPending(null)}
        title={t("admin:companies.rejectConfirmTitle")}
        message={t("admin:companies.rejectConfirm")}
        confirmLabel={t("admin:companies.rejectAction")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleRejectConfirm}
      />
    </>
  );
}
