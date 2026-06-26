import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { getAdminOverview } from "@/services/adminOverview";
import { UserRole } from "@/types/enums";

// ─── Types ────────────────────────────────────────────────────────────────────

interface NavItemDef {
  labelKey: string;
  to: string;
  badge?: number | null;
}

interface NavGroupDef {
  labelKey: string;
  items: NavItemDef[];
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

// ─── Single nav link row ──────────────────────────────────────────────────────

function NavRow({
  item,
  onClose,
  indent = false,
}: {
  item: NavItemDef;
  onClose: () => void;
  indent?: boolean;
}) {
  const { t } = useTranslation("nav");
  return (
    <NavLink
      to={item.to}
      end={item.to === "/dashboard"}
      onClick={onClose}
      className={({ isActive }) =>
        `flex items-center justify-between rounded-sm py-2 text-sm transition ${
          indent ? "pe-3 ps-5" : "px-3"
        } ${
          isActive
            ? "bg-copper/12 font-medium text-copper"
            : "text-white/40 hover:bg-white/5 hover:text-white/70"
        }`
      }
    >
      <span>{t(item.labelKey)}</span>
      {item.badge != null && item.badge > 0 && (
        <span className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-copper px-1 py-px text-[10px] font-semibold text-white">
          {item.badge}
        </span>
      )}
    </NavLink>
  );
}

// ─── Collapsible group ────────────────────────────────────────────────────────

function NavGroup({
  group,
  onClose,
}: {
  group: NavGroupDef;
  onClose: () => void;
}) {
  const { t } = useTranslation("nav");
  const location = useLocation();
  const isAnyChildActive = group.items.some((i) =>
    location.pathname.startsWith(i.to),
  );

  const [userOpen, setUserOpen] = useState(true);
  const open = userOpen || isAnyChildActive;

  return (
    <div>
      <button
        type="button"
        onClick={() => setUserOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-sm px-3 py-1.5 transition hover:bg-white/4"
      >
        <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-white/28">
          {t(group.labelKey)}
        </span>
        <svg
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className={`size-3 shrink-0 text-white/22 transition-transform duration-150 ${
            open ? "rotate-180" : "rotate-0"
          }`}
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="mt-0.5 space-y-0.5">
            {group.items.map((item) => (
              <NavRow key={item.to} item={item} onClose={onClose} indent />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { t } = useTranslation("nav");
  const { user } = useAuth();

  const [pendingCompanies, setPendingCompanies] = useState<number | null>(null);
  const [pendingJobs, setPendingJobs] = useState<number | null>(null);
  const [newApplications, setNewApplications] = useState<number | null>(null);

  useEffect(() => {
    if (user?.role !== UserRole.ADMIN) return;
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then((data) => {
        setPendingCompanies(data.inbox.pending_companies);
        setPendingJobs(data.inbox.pending_jobs);
        setNewApplications(data.inbox.new_applications);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [user?.role]);

  const adminGroups: NavGroupDef[] = [
    {
      labelKey: "nav:sectionEmployers",
      items: [
        { labelKey: "nav:companies", to: "/admin/companies", badge: pendingCompanies },
        { labelKey: "nav:jobs", to: "/admin/jobs", badge: pendingJobs },
      ],
    },
    {
      labelKey: "nav:sectionRecruitment",
      items: [
        { labelKey: "nav:candidates", to: "/admin/candidates" },
        {
          labelKey: "nav:applications",
          to: "/admin/applications",
          badge: newApplications,
        },
      ],
    },
  ];

  const companyNav: NavItemDef[] = [
    { labelKey: "nav:dashboard", to: "/dashboard" },
    { labelKey: "nav:myJobs", to: "/company/jobs" },
  ];

  const candidateNav: NavItemDef[] = [
    { labelKey: "nav:dashboard", to: "/dashboard" },
    { labelKey: "nav:browseJobs", to: "/jobs" },
    { labelKey: "nav:myApplications", to: "/candidate/applications" },
    { labelKey: "nav:myProfile", to: "/candidate/profile" },
  ];

  const flatNav = user?.role === UserRole.CANDIDATE ? candidateNav : companyNav;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const navContent = (
    <nav className="flex-1 p-3">
      {user?.role === UserRole.ADMIN ? (
        <div className="space-y-1">
          <NavRow
            item={{ labelKey: "nav:dashboard", to: "/dashboard" }}
            onClose={onClose}
          />
          <div className="my-2 border-t border-white/6" />
          <div className="space-y-3">
            {adminGroups.map((group) => (
              <NavGroup key={group.labelKey} group={group} onClose={onClose} />
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-0.5">
          {flatNav.map((item) => (
            <NavRow key={item.to} item={item} onClose={onClose} />
          ))}
        </div>
      )}
    </nav>
  );

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`
          fixed inset-y-0 start-0 z-30 flex w-52 flex-col border-e border-white/8
          bg-void transition-transform duration-200 ease-in-out
          md:static md:translate-x-0
          ${isOpen ? "translate-x-0" : "max-md:ltr:-translate-x-full max-md:rtl:translate-x-full"}
        `}
      >
        <div className="flex items-center justify-between border-b border-white/8 px-4 py-3 md:hidden">
          <span className="text-sm text-white/45">{t("nav:menu")}</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm p-1 text-white/30 transition hover:bg-white/5 hover:text-white/60"
            aria-label={t("nav:closeNavigation")}
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        {navContent}
      </aside>
    </>
  );
}
