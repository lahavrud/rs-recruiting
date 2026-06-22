import { useEffect } from "react";

import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/api";

interface NavItem {
  labelKey: string;
  to: string;
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { t } = useTranslation('nav');
  const { user } = useAuth();

  const adminNav: NavItem[] = [
    { labelKey: "nav:dashboard", to: "/dashboard" },
    { labelKey: "nav:companies", to: "/admin/companies" },
    { labelKey: "nav:jobs", to: "/admin/jobs" },
    { labelKey: "nav:applications", to: "/admin/applications" },
    { labelKey: "nav:candidates", to: "/admin/candidates" },
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
            `block rounded-sm px-3 py-2 text-sm transition ${
              isActive
                ? "bg-copper/12 font-medium text-copper"
                : "text-white/40 hover:bg-white/5 hover:text-white/70"
            }`
          }
        >
          {t(item.labelKey)}
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
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {navContent}
      </aside>
    </>
  );
}
