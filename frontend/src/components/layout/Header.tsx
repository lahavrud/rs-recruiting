import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Logo from "@/components/ui/Logo";
import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/enums";

interface HeaderProps {
  onMenuToggle: () => void;
}

export default function Header({ onMenuToggle }: HeaderProps) {
  const { t } = useTranslation(['auth', 'nav', 'ui']);
  const { user, logout } = useAuth();

  const roleLabel =
    user?.role === UserRole.ADMIN
      ? t("ui:header.roleLabel.ADMIN")
      : user?.role === UserRole.COMPANY
        ? t("ui:header.roleLabel.COMPANY")
        : t("ui:header.roleLabel.CANDIDATE");

  return (
    <header className="flex h-14 items-center justify-between border-b border-white/8 bg-void px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuToggle}
          className="rounded-sm p-1.5 text-white/30 transition hover:bg-white/5 hover:text-white/60 md:hidden"
          aria-label={t("nav:toggleNavigation")}
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <Link to="/dashboard" className="flex items-center gap-2.5 transition hover:opacity-80">
          <Logo size={26} />
          <span className="text-sm font-medium text-white/55">{t("auth:appName")}</span>
        </Link>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        <span className="hidden max-w-[160px] truncate text-sm text-white/35 sm:block">
          {user?.email}
        </span>
        <span className="hidden rounded-full border border-white/10 px-2.5 py-0.5 text-xs text-white/35 sm:inline-block">
          {roleLabel}
        </span>
        <button
          onClick={logout}
          className="rounded-sm border border-white/15 px-3 py-1.5 text-sm text-white/40 transition hover:border-white/30 hover:text-white/70"
        >
          {t("ui:header.logout")}
        </button>
      </div>
    </header>
  );
}
