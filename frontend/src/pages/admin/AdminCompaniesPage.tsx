import { Fragment, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import PageHeader from "@/components/ui/PageHeader";
import SearchInput from "@/components/ui/SearchInput";
import { useDebounce } from "@/hooks/useDebounce";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { deleteCompany, deleteOrphanCompany } from "@/services/adminCompanies";
import { getAdminOverview } from "@/services/adminOverview";
import type { CompanyProfileRead } from "@/types/auth";

import CompanyActiveTab from "./components/CompanyActiveTab";
import CompanyInvitesTab from "./components/CompanyInvitesTab";
import CompanyPendingTab from "./components/CompanyPendingTab";
import CompanyRecordPane from "./components/CompanyRecordPane";
import CreateCompanyDialog from "./components/CreateCompanyDialog";
import EditCompanyDialog from "./components/EditCompanyDialog";

type Tab = "active" | "pending" | "invites";

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminCompaniesPage() {
  const { t } = useTranslation(["admin", "common"]);
  usePageTitle(t("admin:companies.title"));
  const toast = useToast();
  const navigate = useNavigate();
  const { id: rawId } = useParams<{ id?: string }>();
  const selectedId = rawId != null && !Number.isNaN(Number(rawId)) ? Number(rawId) : null;

  const [view, setView] = useState<Tab>(() => {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "active" || v === "pending" || v === "invites") return v;
    return "active";
  });
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [isCreating, setIsCreating] = useState(false);
  const [isInviting, setIsInviting] = useState(() => {
    return new URLSearchParams(window.location.search).get("action") === "invite";
  });
  // Record-pane–triggered edit/delete (list-row actions stay in CompanyActiveTab).
  const [editing, setEditing] = useState<CompanyProfileRead | null>(null);
  const [deletePending, setDeletePending] = useState<CompanyProfileRead | null>(null);
  const [isPendingMutation, setIsPendingMutation] = useState(false);
  // Increment to force CompanyActiveTab to reload its list.
  const [listReloadKey, setListReloadKey] = useState(0);

  // Strip bootstrap query params after consumption.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has("action") || url.searchParams.has("view")) {
      url.searchParams.delete("action");
      url.searchParams.delete("view");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }, []);

  // Tab counts from the overview endpoint (exact counts, no capping).
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [activeCount, setActiveCount] = useState<number | null>(null);
  const [invitesCount, setInvitesCount] = useState<number | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then((data) => {
        setPendingCount(data.inbox.pending_companies);
        setActiveCount(data.stats.active_companies);
        setInvitesCount(data.inbox.pending_invites);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  function handleInvite() {
    setView("invites");
    setIsInviting(true);
  }

  function handleSelect(id: number) {
    navigate(`/admin/companies/${id}`);
  }

  async function handleDeleteFromPane() {
    if (!deletePending) return;
    setIsPendingMutation(true);
    try {
      // deletePending is a CompanyProfileRead; check user_id to pick the right endpoint.
      if (deletePending.user_id != null) {
        await deleteCompany(deletePending.user_id);
      } else {
        await deleteOrphanCompany(deletePending.id);
      }
      toast.success(t("admin:companies.deletedToast"));
      setDeletePending(null);
      setListReloadKey((k) => k + 1);
      navigate("/admin/companies");
    } catch {
      toast.error(t("admin:companies.active.deleteError"));
    } finally {
      setIsPendingMutation(false);
    }
  }

  const viewCounts: Record<Tab, number | null> = {
    pending: pendingCount,
    active: activeCount,
    invites: invitesCount,
  };

  const header = (
    <PageHeader
      eyebrow={t("admin:companies.title")}
      subtitle={t("admin:companies.subtitle")}
      action={
        <div className="flex w-full gap-2 sm:w-auto sm:items-center">
          <Button
            size="sm"
            onClick={() => setIsCreating(true)}
          >
            {t("admin:companies.newCompany")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleInvite}
          >
            {t("admin:companies.inviteForm.newInviteButton")}
          </Button>
        </div>
      }
    />
  );

  const tabPills = (
    <div className="mb-4 flex flex-wrap justify-center gap-1.5">
      {(["active", "pending", "invites"] as Tab[]).map((key, i) => {
        const active = view === key;
        const n = viewCounts[key];
        return (
          <Fragment key={key}>
            <button
              type="button"
              onClick={() => setView(key)}
              aria-pressed={active}
              className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition active:scale-[0.97] ${
                active
                  ? "bg-copper text-white shadow-sm shadow-black/30"
                  : "border border-white/12 text-white/60 hover:border-white/30 hover:text-white/85"
              }`}
            >
              <span>{t(`admin:companies.tabs.${key}`)}</span>
              <span
                className={`inline-flex min-w-[1.5rem] items-center justify-center rounded-full px-1.5 text-[10px] font-semibold ${
                  active ? "bg-white/20 text-white" : "bg-white/8 text-white/55"
                }`}
              >
                {n == null ? "—" : String(n)}
              </span>
            </button>
            {/* Mobile-only flex-wrap break after the first pill. */}
            {i === 0 && <div className="basis-full sm:hidden" aria-hidden="true" />}
          </Fragment>
        );
      })}
    </div>
  );

  const searchBar = (
    <div className="mb-3">
      <SearchInput
        value={query}
        onChange={setQuery}
        placeholder={
          view === "invites"
            ? t("admin:companies.inviteList.searchPlaceholder")
            : t("admin:companies.searchPlaceholder")
        }
        isClearable
      />
    </div>
  );

  const filterChips = query.trim() ? (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <ActiveFilterChip
        label={`${t("common:search")}: "${query.trim()}"`}
        onRemove={() => setQuery("")}
      />
    </div>
  ) : null;

  const dialogs = (
    <>
      <CreateCompanyDialog
        open={isCreating}
        onClose={() => setIsCreating(false)}
        onCreated={(profile) => {
          setIsCreating(false);
          navigate(`/admin/companies/${profile.id}`);
        }}
      />
      <EditCompanyDialog
        profile={editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          toast.success(t("admin:companies.savedToast"));
          setEditing(null);
          setListReloadKey((k) => k + 1);
        }}
      />
      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin:companies.deleteConfirmTitle", {
          name: deletePending?.name ?? "",
        })}
        message={t("admin:companies.active.deleteConfirm")}
        confirmLabel={t("admin:companies.deleteAction")}
        variant="danger"
        isPending={isPendingMutation}
        onConfirm={handleDeleteFromPane}
      />
    </>
  );

  if (selectedId == null) {
    return (
      <div>
        <h1 data-page-heading className="sr-only">
          {t("admin:companies.title")}
        </h1>
        {header}
        {tabPills}
        {searchBar}
        {filterChips}

        {view === "active" && (
          <CompanyActiveTab
            query={debouncedQuery}
            selectedId={null}
            onSelect={handleSelect}
            reloadKey={listReloadKey}
          />
        )}
        {view === "pending" && <CompanyPendingTab query={debouncedQuery} />}
        {view === "invites" && (
          <CompanyInvitesTab
            query={debouncedQuery}
            isExternalOpen={isInviting}
            onExternalClose={() => setIsInviting(false)}
          />
        )}
        {dialogs}
      </div>
    );
  }

  return (
    <SplitPaneLayout
      recordPresent={selectedId != null}
      showListLabel={t("admin:companies.record.showList")}
      hideListLabel={t("admin:companies.record.hideList")}
      rail={
        <>
          <h1 data-page-heading className="sr-only">
            {t("admin:companies.title")}
          </h1>
          {header}
          <div className="mb-3">{searchBar}</div>
          {filterChips}
          <div className="min-h-0 flex-1 overflow-y-auto">
            <CompanyActiveTab
              query={debouncedQuery}
              selectedId={selectedId}
              onSelect={handleSelect}
              reloadKey={listReloadKey}
            />
          </div>
        </>
      }
      record={
        <CompanyRecordPane
          companyId={selectedId}
          onEdit={setEditing}
          onDelete={setDeletePending}
        />
      }
    >
      {dialogs}
    </SplitPaneLayout>
  );
}
