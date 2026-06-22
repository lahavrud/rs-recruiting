import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

function IconArrow() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className="size-4"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M5 12h14m0 0-5-5m5 5-5 5"
      />
    </svg>
  );
}

export function BrowseJobsCta({ hasApps }: { hasApps: boolean }) {
  const { t } = useTranslation('dashboard');
  return (
    <section className="relative overflow-hidden rounded-2xl border border-copper/25 bg-gradient-to-br from-copper/15 via-card-raised to-card p-6 sm:p-8">
      {/* Decorative copper glow — pseudo-element via inline span so we
          don't have to touch index.css. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -end-12 -top-12 size-48 rounded-full bg-copper/15 blur-3xl"
      />
      <div className="relative">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          {t("dashboard:candidate.browseCta.eyebrow")}
        </p>
        <h2 className="mt-2 text-lg font-semibold text-white/90 sm:text-xl">
          {hasApps
            ? t("dashboard:candidate.browseCta.titleReturning")
            : t("dashboard:candidate.browseCta.titleFirst")}
        </h2>
        <p className="mt-1 max-w-prose text-sm text-white/55">
          {t("dashboard:candidate.browseCta.body")}
        </p>
        <Link
          to="/jobs"
          className="mt-4 inline-flex items-center gap-2 rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white transition hover:bg-gold"
        >
          {t("dashboard:candidate.browseCta.action")}
          <IconArrow />
        </Link>
      </div>
    </section>
  );
}
