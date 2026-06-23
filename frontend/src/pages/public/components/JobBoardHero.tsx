import type { CSSProperties } from "react";

import { useTranslation } from "react-i18next";

import SearchInput from "@/components/ui/SearchInput";
import { useImageLoaded } from "@/hooks/useImageLoaded";

function rise(delay = "0s", duration = "0.8s"): CSSProperties {
  return { animation: `text-rise ${duration} cubic-bezier(0.16, 1, 0.3, 1) ${delay} both` };
}
function revealUp(delay = "0s"): CSSProperties {
  return { animation: `reveal-up 0.75s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both` };
}
function ruleDraw(delay = "0s"): CSSProperties {
  return { animation: `line-expand-h 0.7s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both`, transformOrigin: "right" };
}

interface JobBoardHeroProps {
  initialQuery: string;
  onSearch: (v: string) => void;
}

export default function JobBoardHero({ initialQuery, onSearch }: JobBoardHeroProps) {
  const { t } = useTranslation('publicJobs');
  const heroBgLoaded = useImageLoaded("/property-exterior.webp");

  return (
    <section className="relative overflow-hidden bg-void pt-28 pb-14 sm:pt-32 sm:pb-16">
      {/* Property image background — CSS bg has no native load event, so
          we preload it via useImageLoaded and fade in once available to
          avoid a dark-overlay-over-nothing flash on slow networks. */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: "image-set(url('/property-exterior.webp') type('image/webp'), url('/property-exterior.jpg') type('image/jpeg'))",
          backgroundSize: "cover",
          backgroundPosition: "center 40%",
          opacity: heroBgLoaded ? 1 : 0,
          transition: "opacity 700ms ease-out",
        }}
      />
      <div className="absolute inset-0 bg-void/88" />
      {/* Copper glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 90% at 50% -10%, color-mix(in srgb, var(--color-copper) 11%, transparent), transparent)",
        }}
      />

      <div className="relative mx-auto max-w-4xl px-6">
        {/* Eyebrow */}
        <div className="h-px w-8 bg-copper/45" style={ruleDraw("0.1s")} />
        <div className="mt-3 overflow-hidden">
          <p
            className="text-[10px] font-semibold uppercase tracking-widest text-copper/75"
            style={rise("0.2s", "0.55s")}
          >
            RS Recruiting
          </p>
        </div>

        {/* Headline */}
        <div className="mt-5 overflow-hidden">
          <h1
            className="text-3xl font-semibold leading-snug text-white/92 sm:text-4xl"
            style={rise("0.3s")}
          >
            {t("publicJobs:board.title")}
          </h1>
        </div>

        {/* Subtitle */}
        <p
          className="mt-3 max-w-xl text-sm leading-relaxed text-white/45"
          style={revealUp("0.5s")}
        >
          {t("publicJobs:board.subtitle")}
        </p>

        {/* Search bar */}
        <div className="mt-8 max-w-lg" style={revealUp("0.65s")}>
          <SearchInput
            initialValue={initialQuery}
            onChange={onSearch}
            placeholder={t("publicJobs:board.searchPlaceholder")}
          />
        </div>
      </div>
    </section>
  );
}
