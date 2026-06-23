import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import LandingClients from "./LandingClients";
import LandingSilk from "./LandingSilk";

interface LandingHeroProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onSearchSubmit: (e: React.FormEvent) => void;
}

/* Hero: copy on the right (RTL), molten-silk WebGL backdrop filling the void
   on the left, with the client-logo ribbon riding near — but lifted off —
   the bottom edge. */
export default function LandingHero({
  searchQuery,
  onSearchChange,
  onSearchSubmit,
}: LandingHeroProps) {
  const { t } = useTranslation(["common", "landing"]);

  return (
    <section className="relative flex h-dvh flex-col overflow-hidden bg-void">
      {/* Full-bleed stage: spans the viewport width and the full height
          between the navbar and the client ribbon, so the silk backdrop can
          stretch edge to edge while the copy stays in the content column.
          min-h-0 lets it shrink (and the column's overflow-hidden clip) so
          the section stays exactly one viewport tall on short/non-maximized
          windows — the ribbon below never spills past the fold. */}
      <div className="relative z-10 min-h-0 flex-1">
        <LandingSilk />

        <div className="relative mx-auto flex h-full w-full max-w-7xl flex-col justify-center overflow-hidden px-6 pb-4 pt-[clamp(5rem,10dvh,8rem)] sm:px-12">
          <div className="max-w-3xl">
            <h1 className="sr-only">{t("landing:seo.h1")}</h1>

            <div className="flex items-center gap-4">
              <span className="brass-hairline h-px w-12 shrink-0 sm:w-16" />
              <p className="text-xs font-medium tracking-widest text-copper sm:text-sm">
                {t("landing:hero.eyebrow")}
              </p>
            </div>

            {/* Fluid headline: min(vw, dvh) tracks whichever axis is more
              constrained so it never overflows a narrow or short window. */}
            <div className="font-display mt-[clamp(0.75rem,2.5dvh,1.75rem)] text-[clamp(1.55rem,min(7vw,6dvh),4.25rem)] font-black leading-[1.08] text-white/95">
              <span className="block">{t("landing:hero.statementLine1")}</span>
              <span className="block">{t("landing:hero.statementLine2")}</span>
              <span className="block text-gold">
                {t("landing:hero.statementKicker")}
              </span>
            </div>

            <p className="mt-[clamp(0.6rem,2.5dvh,1.75rem)] max-w-md text-[clamp(0.85rem,0.4vw+1.3dvh,1.125rem)] font-light leading-relaxed text-white/55">
              {t("landing:hero.tagline")}
              {/* Mobile gets only the opening statement */}
              <span className="hidden sm:inline"> {t("landing:hero.taglineMore")}</span>
            </p>

            {/* Search input */}
            <form
              onSubmit={onSearchSubmit}
              className="mt-[clamp(0.85rem,3dvh,2.25rem)] max-w-xl"
            >
              <div className="group relative">
                <div className="brass-hairline absolute -top-px inset-x-0 h-px opacity-50 transition-opacity duration-500 group-focus-within:opacity-100" />
                <div className="flex items-stretch border border-white/12 bg-well/85 shadow-2xl backdrop-blur-md transition-colors duration-300 focus-within:border-copper/45">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder={t("landing:hero.searchPlaceholder")}
                    className="min-w-0 flex-1 bg-transparent py-4.5 pe-4 ps-5 text-base text-white/90 placeholder:text-white/30 focus:outline-none"
                  />
                  <button
                    type="submit"
                    aria-label={t("landing:hero.searchSubmit")}
                    className="flex w-14 shrink-0 items-center justify-center bg-copper text-white transition-colors duration-300 hover:bg-gold sm:w-16"
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <circle cx="11" cy="11" r="8" />
                      <path d="m21 21-4.35-4.35" />
                    </svg>
                  </button>
                </div>
              </div>
            </form>

            {/* Dual paths: candidates act, companies start a conversation */}
            <div className="mt-[clamp(0.6rem,2dvh,1.5rem)] flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              <Link
                to="/jobs"
                className="font-medium text-copper transition-colors hover:text-gold"
              >
                {t("landing:hero.allJobs")} ←
              </Link>
              <span aria-hidden="true" className="h-3.5 w-px bg-white/15" />
              <span className="text-white/35">
                {t("landing:hero.companiesPrompt")}{" "}
                <Link
                  to="/contact"
                  className="text-white/55 underline decoration-white/20 underline-offset-4 transition-colors hover:text-white/85 hover:decoration-copper/60"
                >
                  {t("landing:hero.companiesLink")}
                </Link>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Client-logo ribbon, lifted off the bottom edge by the spacer below so
          it sits within the hero rather than pinned to the very bottom. */}
      {/* Reserved margin between the hero copy and the ribbon. It sits
          outside the clipped copy column, so even when the copy compresses to
          its floor on a short window this gap is never eaten into.
          Height comes from the shared --landing-ribbon-gap custom property
          (index.css), which LandingSilk's host inset also reads. */}
      <div aria-hidden="true" className="h-[var(--landing-ribbon-gap)] shrink-0" />

      <LandingClients />
      <div aria-hidden="true" className="h-[clamp(1.25rem,4dvh,3.5rem)] shrink-0" />
    </section>
  );
}
