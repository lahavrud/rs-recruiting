import { Fragment, useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import PageHeader from "@/components/ui/PageHeader";
import SearchInput from "@/components/ui/SearchInput";
import { useDebounce } from "@/hooks/useDebounce";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import {
  getActiveCompanies,
  getCompanyProfile,
  getPendingCompanies,
} from "@/services/adminCompanies";
import { getInvites } from "@/services/adminInvites";
import type { CompanyProfileRead } from "@/types/api";
import { InviteTokenStatus } from "@/types/api";

import CompanyActiveTab from "./components/CompanyActiveTab";
import CompanyInvitesTab from "./components/CompanyInvitesTab";
import CompanyPendingTab from "./components/CompanyPendingTab";
import CreateCompanyDialog from "./components/CreateCompanyDialog";

type Tab = "active" | "pending" | "invites";

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminCompaniesPage() {
  const { t } = useTranslation(['admin', 'common']);
  usePageTitle(t("admin:companies.title"));
  const toast = useToast();
  const [view, setView] = useState<Tab>(() => {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "active" || v === "pending" || v === "invites") return v;
    return "active";
  });
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [creating, setCreating] = useState(false);
  const [inviting, setInviting] = useState(() => {
    return new URLSearchParams(window.location.search).get("action") === "invite";
  });
  const [externalDetail, setExternalDetail] = useState<CompanyProfileRead | null>(null);

  // Auto-open company detail when navigated from another page via ?detail=<profile_id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    const ctrl = new AbortController();
    window.history.replaceState({}, "", window.location.pathname);
    getCompanyProfile(Number(id), ctrl.signal)
      .then((profile) => {
        setView("active");
        setExternalDetail(profile);
      })
      .catch((e) => {
        if (axios.isCancel(e)) return;
        toast.error(t("common:genericError"));
      });
    return () => ctrl.abort();
  }, [t, toast]);

  // Strip the bootstrap `?action=` and `?view=` params after they've been
  // consumed so a hard refresh doesn't re-trigger them.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has("action") || url.searchParams.has("view")) {
      url.searchParams.delete("action");
      url.searchParams.delete("view");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }, []);

  function handleInvite() {
    setView("invites");
    setInviting(true);
  }

  // View counts shown in the segmented pills. First-page fetches; capped
  // counts surface as "N+".
  type ViewCount = { n: number; capped: boolean } | null;
  const [pendingCount, setPendingCount] = useState<ViewCount>(null);
  const [activeCount, setActiveCount] = useState<ViewCount>(null);
  const [invitesCount, setInvitesCount] = useState<ViewCount>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    function toCount<T>(p: { items: T[]; next_cursor: string | null }): ViewCount {
      return { n: p.items.length, capped: p.next_cursor != null };
    }
    getPendingCompanies({ limit: 100 }, ctrl.signal)
      .then((p) => setPendingCount(toCount(p)))
      .catch(() => {});
    getActiveCompanies({ limit: 100 }, ctrl.signal)
      .then((p) => setActiveCount(toCount(p)))
      .catch(() => {});
    getInvites(
      { status: InviteTokenStatus.PENDING, limit: 100 },
      ctrl.signal,
    )
      .then((p) => setInvitesCount(toCount(p)))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  function formatCount(c: ViewCount): string {
    if (c == null) return "—";
    return c.capped ? `${c.n}+` : String(c.n);
  }

  const viewCounts: Record<Tab, ViewCount> = {
    pending: pendingCount,
    active: activeCount,
    invites: invitesCount,
  };


  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin:companies.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin:companies.title")}
        subtitle={t("admin:companies.subtitle")}
        action={
          <div className="flex w-full gap-2 sm:w-auto sm:items-center">
            <button
              onClick={() => setCreating(true)}
              className="flex-1 rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold sm:flex-initial"
            >
              {t("admin:companies.newCompany")}
            </button>
            <button
              onClick={handleInvite}
              className="flex-1 rounded-sm border border-copper/40 px-4 py-2 text-sm font-medium text-copper/80 transition hover:border-copper hover:text-copper sm:flex-initial"
            >
              {t("admin:companies.inviteForm.newInviteButton")}
            </button>
          </div>
        }
      />

      {/* View pills — primary axis of the page, with live counts.
          On mobile, the active-companies pill sits on its own row above
          the other two; on `sm+` all three share a single centered row. */}
      <div className="mb-4 flex flex-wrap justify-center gap-1.5">
        {(["active", "pending", "invites"] as Tab[]).map((key, i) => {
          const active = view === key;
          const c = viewCounts[key];
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
                    active
                      ? "bg-white/20 text-white"
                      : "bg-white/8 text-white/55"
                  }`}
                >
                  {formatCount(c)}
                </span>
              </button>
              {/* Mobile-only flex-wrap break after the first pill. */}
              {i === 0 && (
                <div className="basis-full sm:hidden" aria-hidden="true" />
              )}
            </Fragment>
          );
        })}
      </div>

      {/* Search */}
      <div className="mb-3">
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder={
            view === "invites"
              ? t("admin:companies.inviteList.searchPlaceholder")
              : t("admin:companies.searchPlaceholder")
          }
          clearable
        />
      </div>

      {query.trim() && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <ActiveFilterChip
            label={`${t("common:search")}: "${query.trim()}"`}
            onRemove={() => setQuery("")}
          />
        </div>
      )}

      {view === "active" && (
        <CompanyActiveTab
          query={debouncedQuery}
          externalDetail={externalDetail}
          onExternalDetailClose={() => setExternalDetail(null)}
        />
      )}
      {view === "pending" && <CompanyPendingTab query={debouncedQuery} />}
      {view === "invites" && (
        <CompanyInvitesTab
          query={debouncedQuery}
          externalOpen={inviting}
          onExternalClose={() => setInviting(false)}
        />
      )}

      <CreateCompanyDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(profile) => {
          setCreating(false);
          setView("active");
          setExternalDetail(profile);
        }}
      />
    </div>
  );
}
