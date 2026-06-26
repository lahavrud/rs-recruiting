import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { getAdminOverview } from "@/services/adminOverview";
import { UserRole } from "@/types/enums";

interface NavItem {
  labelKey: string;
  to: string;
  /** Pending-action count. Shown as a copper pill when > 0, hidden when 0 or null (loading). */
  badge?: number | null;
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

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

  const reviewQueueBadge =
    pendingCompanies != null && pendingJobs != null && newApplications != null
      ? pendingCompanies + pendingJobs + newApplications
      : null;

  const adminNav: NavItem[] = [
    { labelKey: "nav:dashboard", to: "/dashboard" },
    { labelKey: "nav:companies", to: "/admin/companies", badge: pendingCompanies },
    { labelKey: "nav:jobs", to: "/admin/jobs", badge: pendingJobs },
    { labelKey: "nav:applications", to: "/admin/applications", badge: newApplications },
    { labelKey: "nav:candidates", to: "/admin/candidates" },
    { labelKey: "nav:reviewQueue", to: "/admin/review", badge: reviewQueueBadge },
  ];

  const companyNav: NavItem[] = [
    { labelKey: "nav:dashboard", to: "/dashboard" },
    { labelKey: "nav:myJobs", to: "/company/jobs" },
  ];

  const candidateNav: NavItem[] = [
    { labelKey: "nav:dashboard", to: "/dashboard" },
    { labelKey: "nav:browseJobs", to: "/jobs" },
    { labelKey: "nav:myApplications", to: "/candidate/applications" },
    { labelKey: "nav:myProfile", to: "/candidate/profile" },
  ];

  const navItems =
    user?.role === UserRole.ADMIN
      ? adminNav
      : user?.role === UserRole.CANDIDATE
        ? candidateNav
        : companyNav;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const navContent = (
    <nav className="flex-1 space-y-0.5 p-3">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/dashboard"}
          onClick={onClose}
          className={({ isActive }) =>
            `flex items-center justify-between rounded-sm px-3 py-2 text-sm transition ${
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
      ))}
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
