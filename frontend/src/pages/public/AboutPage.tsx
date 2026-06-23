import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import { useImageLoaded } from "@/hooks/useImageLoaded";


/* ── Intersection-observer reveal hook ───────────────────────────────────── */
function useReveal(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { setIsVisible(true); return; }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setIsVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, isVisible] as const;
}

/* ── Animation helpers ───────────────────────────────────────────────────── */

/** General reveal: fade + settle (body text, secondary elements) */
function revealUp(isVisible: boolean, delay = "0s", duration = "0.8s"): CSSProperties {
  return isVisible
    ? { animation: `reveal-up ${duration} cubic-bezier(0.22, 1, 0.36, 1) ${delay} both` }
    : { opacity: 0 };
}

/** Text-rise: slides up from below its overflow:hidden container (headings) */
function rise(isVisible: boolean, delay = "0s", duration = "0.85s"): CSSProperties {
  return isVisible
    ? { animation: `text-rise ${duration} cubic-bezier(0.16, 1, 0.3, 1) ${delay} both` }
    : { transform: "translateY(110%)" };
}

/** Copper rule expands from the reading-start side (right in RTL) */
function ruleDraw(isVisible: boolean, delay = "0s"): CSSProperties {
  return isVisible
    ? { animation: `line-expand-h 0.75s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both`, transformOrigin: "right" }
    : { transform: "scaleX(0)" };
}

/** Directional slide for asymmetric value rows */
function slideDir(isVisible: boolean, dir: "right" | "left", delay = "0s"): CSSProperties {
  const name = dir === "right" ? "reveal-from-right" : "reveal-from-left";
  return isVisible
    ? { animation: `${name} 0.85s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both` }
    : { opacity: 0 };
}

/* ── Character-by-character text rise (hero headline) ───────────────────── */
function CharRise({
  text,
  baseDelay,
  gap = 0.045,
  isVisible,
  className = "",
}: {
  text: string;
  baseDelay: number;
  gap?: number;
  isVisible: boolean;
  className?: string;
}) {
  const words = text.split(" ");
  // Pre-compute where each word starts in the overall character sequence
  const wordOffsets = words.reduce<number[]>((acc, _w, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + words[i - 1].length + 1);
    return acc;
  }, []);
  return (
    <span className={className}>
      {words.map((word, wi) => (
        <span
          key={wi}
          className="inline-block whitespace-nowrap"
          style={wi > 0 ? { marginInlineStart: "0.28em" } : undefined}
        >
          {word.split("").map((char, ci) => (
            <span key={ci} className="inline-block overflow-hidden align-bottom leading-none">
              <span
                className="inline-block"
                style={rise(isVisible, `${(baseDelay + (wordOffsets[wi] + ci) * gap).toFixed(3)}s`)}
              >
                {char}
              </span>
            </span>
          ))}
        </span>
      ))}
    </span>
  );
}

export default function AboutPage() {
  const { t } = useTranslation(['about', 'http', 'https']);

  /* Reading progress bar */
  const [progress, setProgress] = useState(0);
  /* Hero parallax */
  const [heroShift, setHeroShift] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? (y / max) * 100 : 0);
      setHeroShift(Math.min(y * 0.2, 100));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const [storyRef, isStoryVisible] = useReveal(0.15);
  const [philosophyRef, isPhilosophyVisible] = useReveal(0.3);
  const [valuesRef, isValuesVisible] = useReveal(0.06);
  const [processRef, isProcessVisible] = useReveal(0.1);
  const [statsRef, isStatsVisible] = useReveal(0.2);
  const [faqRef, isFaqVisible] = useReveal(0.08);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  // Hero / story / process backgrounds are CSS `background-image: url(...)`
  // which has no native load event — preload them so the `focus-in` animation
  // doesn't run over an empty rect on slow networks.
  const heroBgLoaded = useImageLoaded("/hero-buildings.webp");
  const isStoryBgLoaded = useImageLoaded("/property-exterior.webp");
  const isProcessBgLoaded = useImageLoaded("/team-meeting.webp");

  const quoteWords = t("about:philosophy.quote").split(" ");

  return (
    <>
      {/* Fixed elements live OUTSIDE the page-enter div so they are never
          inside an ancestor with transform applied (page-in animation uses
          translateY which would create a containing block, trapping fixed
          descendants and making position:fixed relative to the div instead
          of the viewport). */}
      <div
        className="fixed start-0 top-0 z-50 h-px bg-copper/70 transition-none"
        style={{ width: `${progress}%` }}
      />

      <SeoHead
        title={t("about:seo.title")}
        description={t("about:seo.description")}
        canonical={`${SITE_URL}/about`}
        ogImage={`${SITE_URL}/og/about.svg`}
        structuredData={[
          {
            "@context": "https://schema.org",
            "@type": "Organization",
            name: "RS Recruiting",
            url: SITE_URL,
            description: t("about:seo.description"),
            email: "support@rs-recruiting.com",
          },
          {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: Array.from({ length: 10 }, (_, i) => ({
              "@type": "Question",
              name: t(`about:faq.q${i + 1}`),
              acceptedAnswer: {
                "@type": "Answer",
                text: t(`about:faq.a${i + 1}`),
              },
            })),
          },
        ]}
      />

      <div className="overflow-x-hidden bg-void">

      {/* ── Hero — full-bleed, background image ──────────────────────────── */}
      <section className="relative flex min-h-[90vh] flex-col items-center justify-center overflow-hidden px-6 py-24 text-center">
        {/* Mockup background — city image with heavy overlay */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "image-set(url('/hero-buildings.webp') type('image/webp'), url('/hero-buildings.jpg') type('image/jpeg'))",
            backgroundSize: "cover",
            backgroundPosition: "center",
            opacity: heroBgLoaded ? undefined : 0,
            animation: heroBgLoaded
              ? "focus-in 2s cubic-bezier(0.22, 1, 0.36, 1) 0.1s both"
              : undefined,
          }}
        />
        {/* Dark overlay — creates the luxury void feel over the image */}
        <div className="absolute inset-0 bg-void/78" />
        {/* Copper radial glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -5%, color-mix(in srgb, var(--color-copper) 13%, transparent), transparent)",
          }}
        />

        {/* Parallax content */}
        <div
          className="relative"
          style={{ transform: `translateY(${heroShift}px)`, willChange: "transform" }}
        >
          {/* Eyebrow — rule draws first, then text rises */}
          <div className="flex flex-col items-center gap-2">
            <div className="h-px w-10 bg-copper/50" style={ruleDraw(true, "0.25s")} />
            <div className="overflow-hidden">
              <p className="text-xs font-semibold uppercase tracking-widest text-copper/80" style={rise(true, "0.5s", "0.6s")}>
                {t("about:hero.eyebrow")}
              </p>
            </div>
          </div>

          {/* Headline — character-by-character rise */}
          <h1 className="mt-6 text-[clamp(3.5rem,12vw,9rem)] font-light leading-[0.92] tracking-tight">
            <CharRise
              text={t("about:hero.headlineLine1")}
              baseDelay={0.65}
              gap={0.055}
              isVisible={true}
              className="block text-white/90"
            />
            <CharRise
              text={t("about:hero.headlineLine2")}
              baseDelay={0.9}
              gap={0.04}
              isVisible={true}
              className="block text-copper"
            />
          </h1>

          {/* Subtitle */}
          <p
            className="mx-auto mt-10 max-w-xs text-sm leading-relaxed text-white/38"
            style={revealUp(true, "1.4s", "0.7s")}
          >
            {t("about:hero.subtitle")}
          </p>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-10 animate-bounce opacity-20">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth={1.5} className="size-6 text-white">
            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
          </svg>
        </div>
      </section>

      {/* ── Story — property image background ────────────────────────────── */}
      <div ref={storyRef} className="relative overflow-hidden bg-page">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "image-set(url('/property-exterior.webp') type('image/webp'), url('/property-exterior.jpg') type('image/jpeg'))",
            backgroundSize: "cover",
            backgroundPosition: "center",
            animation:
              isStoryVisible && isStoryBgLoaded
                ? "focus-in 1.8s cubic-bezier(0.22, 1, 0.36, 1) both"
                : undefined,
            opacity: isStoryVisible && isStoryBgLoaded ? undefined : 0,
          }}
        />
        <div className="absolute inset-0 bg-page/85" />

        <div className="relative mx-auto max-w-4xl px-6 py-24 sm:py-32">
          <div className="grid gap-12 sm:grid-cols-[3fr_2fr] sm:gap-20">
            <div>
              <div className="h-px w-8 bg-copper/40" style={ruleDraw(isStoryVisible)} />
              <div className="mt-3 overflow-hidden">
                <p className="text-xs font-semibold uppercase tracking-widest text-copper"
                  style={rise(isStoryVisible, "0.1s", "0.6s")}>
                  {t("about:story.eyebrow")}
                </p>
              </div>
              <p className="mt-8 text-xl leading-relaxed text-white/80 sm:text-2xl"
                style={revealUp(isStoryVisible, "0.25s")}>
                {t("about:story.paragraph1")}
              </p>
              <p className="mt-6 text-base leading-relaxed text-white/50"
                style={revealUp(isStoryVisible, "0.45s")}>
                {t("about:story.paragraph2")}
              </p>
            </div>

            <div className="hidden items-start justify-end pt-2 sm:flex"
              style={{ animation: isStoryVisible ? "luxury-fade 2.5s ease-out 0.8s both" : undefined, opacity: isStoryVisible ? undefined : 0 }}>
              <span className="font-wordmark select-none text-[7rem] font-light leading-none text-white/[0.04]">RS</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Philosophy — word-by-word text-rise ──────────────────────────── */}
      <div ref={philosophyRef} className="texture-wave bg-void px-6 py-28 sm:py-44">
        <div className="mx-auto max-w-2xl text-center">
          <blockquote className="text-[clamp(1.6rem,4vw,2.6rem)] font-light leading-relaxed text-white/70">
            {quoteWords.map((word, i) => (
              <span key={i} className="inline-block overflow-hidden align-bottom">
                <span
                  className="inline-block"
                  style={isPhilosophyVisible
                    ? { animation: `text-rise 0.8s cubic-bezier(0.16, 1, 0.3, 1) ${i * 0.08}s both` }
                    : { transform: "translateY(110%)" }}
                >
                  {word}{i < quoteWords.length - 1 ? " " : ""}
                </span>
              </span>
            ))}
          </blockquote>

          <div
            className="mx-auto mt-10 h-px w-20 bg-copper/40"
            style={isPhilosophyVisible
              ? { animation: "line-expand-h 1.6s cubic-bezier(0.22, 1, 0.36, 1) 0.8s both", transformOrigin: "center" }
              : { transform: "scaleX(0)" }}
          />
          <p
            className="mt-5 text-[10px] font-semibold uppercase tracking-widest text-copper/40"
            style={revealUp(isPhilosophyVisible, "1.1s", "0.6s")}
          >
            {t("about:philosophy.attribution")}
          </p>
        </div>
      </div>

      {/* ── Values — asymmetric alternating rows ─────────────────────────── */}
      <div ref={valuesRef} className="bg-page px-6 py-24 sm:py-28">
        <div className="mx-auto max-w-4xl">
          <div className="h-px w-8 bg-copper/40" style={ruleDraw(isValuesVisible)} />
          <div className="mt-3 overflow-hidden">
            <p className="text-xs font-semibold uppercase tracking-widest text-copper"
              style={rise(isValuesVisible, "0.1s", "0.6s")}>
              {t("about:values.eyebrow")}
            </p>
          </div>

          {(
            [
              { tk: "about:values.v1Title", bk: "about:values.v1Body", num: "01", rev: false, d1: "0.2s", d2: "0.32s" },
              { tk: "about:values.v2Title", bk: "about:values.v2Body", num: "02", rev: true,  d1: "0.44s", d2: "0.56s" },
              { tk: "about:values.v3Title", bk: "about:values.v3Body", num: "03", rev: false, d1: "0.68s", d2: "0.8s" },
            ] as const
          ).map((v) => (
            <div
              key={v.num}
              className="group -mx-3 flex cursor-default gap-8 rounded-lg border-t border-white/8 px-3 py-10 transition-colors duration-500 hover:bg-white/[0.02] sm:gap-16"
            >
              {v.rev ? (
                <>
                  <div className="flex-1 pt-2" style={slideDir(isValuesVisible, "right", v.d1)}>
                    <div className="overflow-hidden">
                      <p className="text-lg font-semibold text-white/90 transition-colors duration-500 group-hover:text-white"
                        style={rise(isValuesVisible, v.d1)}>
                        {t(v.tk)}
                      </p>
                    </div>
                    <p className="mt-2 leading-relaxed text-white/45">{t(v.bk)}</p>
                  </div>
                  <div className="w-14 shrink-0 self-end sm:w-20" style={slideDir(isValuesVisible, "left", v.d2)}>
                    <span className="font-wordmark select-none text-6xl font-light leading-none text-copper/15 transition-colors duration-700 group-hover:text-copper/30 sm:text-8xl">
                      {v.num}
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className="w-14 shrink-0 sm:w-20" style={slideDir(isValuesVisible, "right", v.d1)}>
                    <span className="font-wordmark select-none text-6xl font-light leading-none text-copper/15 transition-colors duration-700 group-hover:text-copper/30 sm:text-8xl">
                      {v.num}
                    </span>
                  </div>
                  <div className="flex-1 pt-2" style={slideDir(isValuesVisible, "left", v.d2)}>
                    <div className="overflow-hidden">
                      <p className="text-lg font-semibold text-white/90 transition-colors duration-500 group-hover:text-white"
                        style={rise(isValuesVisible, v.d2)}>
                        {t(v.tk)}
                      </p>
                    </div>
                    <p className="mt-2 leading-relaxed text-white/45">{t(v.bk)}</p>
                  </div>
                </>
              )}
            </div>
          ))}
          <div className="border-t border-white/8" />
        </div>
      </div>

      {/* ── Process — team image background ──────────────────────────────── */}
      <div ref={processRef} className="relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "image-set(url('/team-meeting.webp') type('image/webp'), url('/team-meeting.jpg') type('image/jpeg'))",
            backgroundSize: "cover",
            backgroundPosition: "center 45%",
            animation:
              isProcessVisible && isProcessBgLoaded
                ? "focus-in 1.8s cubic-bezier(0.22, 1, 0.36, 1) both"
                : undefined,
            opacity: isProcessVisible && isProcessBgLoaded ? undefined : 0,
          }}
        />
        <div className="absolute inset-0 bg-card/90" />

        <div className="relative mx-auto max-w-4xl px-6 py-20 sm:py-24">
          <div className="h-px w-8 bg-copper/40" style={ruleDraw(isProcessVisible)} />
          <div className="mt-3 overflow-hidden">
            <p className="text-xs font-semibold uppercase tracking-widest text-copper"
              style={rise(isProcessVisible, "0.1s", "0.6s")}>
              {t("about:howItWorks.eyebrow")}
            </p>
          </div>
          <div className="mt-5 overflow-hidden">
            <p className="text-xl font-semibold text-white/90 sm:text-2xl"
              style={rise(isProcessVisible, "0.2s")}>
              {t("about:howItWorks.headline")}
            </p>
          </div>

          <ol className="mt-12 grid gap-10 sm:grid-cols-3 sm:gap-8">
            {(
              [
                { tk: "about:howItWorks.step1Title", bk: "about:howItWorks.step1Body", num: 1, d: "0.32s" },
                { tk: "about:howItWorks.step2Title", bk: "about:howItWorks.step2Body", num: 2, d: "0.5s" },
                { tk: "about:howItWorks.step3Title", bk: "about:howItWorks.step3Body", num: 3, d: "0.68s" },
              ] as const
            ).map((s) => (
              <li key={s.num}
                className="group relative ps-10 transition-transform duration-300 hover:-translate-y-1"
                style={revealUp(isProcessVisible, s.d)}>
                <span className="absolute start-0 top-0.5 flex size-6 items-center justify-center rounded-full border border-copper/40 text-[10px] font-semibold text-copper transition-colors duration-300 group-hover:border-copper group-hover:bg-copper/10">
                  {s.num}
                </span>
                <div className="overflow-hidden">
                  <p className="font-semibold text-white/85"
                    style={rise(isProcessVisible, s.d)}>
                    {t(s.tk)}
                  </p>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-white/45">{t(s.bk)}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* ── Stats ────────────────────────────────────────────────────────── */}
      <div ref={statsRef} className="bg-card-raised px-6 py-16 sm:py-20">
        <div className="mx-auto max-w-4xl">
          <div className="overflow-hidden text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-copper"
              style={rise(isStatsVisible, "0s", "0.6s")}>
              {t("about:stats.eyebrow")}
            </p>
          </div>
          <div className="mt-10 grid grid-cols-3">
            {(
              [
                { lk: "about:stats.placementsLabel", d: "0.2s" },
                { lk: "about:stats.companiesLabel",  d: "0.4s" },
                { lk: "about:stats.experienceLabel", d: "0.6s" },
              ] as const
            ).map((s) => (
              <div key={s.lk}
                className="border-s border-white/10 px-4 text-center first:border-s-0 sm:px-8"
                style={revealUp(isStatsVisible, s.d, "0.9s")}>
                <p className="text-5xl font-semibold text-white/75 sm:text-6xl">—</p>
                <p className="mt-3 text-xs text-white/35">{t(s.lk)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <div ref={faqRef} className="bg-card px-6 py-20 sm:py-28">
        <div className="mx-auto max-w-3xl">
          <div className="h-px w-8 bg-copper/40" style={ruleDraw(isFaqVisible)} />
          <div className="mt-3 overflow-hidden">
            <p className="text-xs font-semibold uppercase tracking-widest text-copper"
              style={rise(isFaqVisible, "0.1s", "0.6s")}>
              {t("about:faq.eyebrow")}
            </p>
          </div>
          <div className="mt-3 overflow-hidden">
            <p className="text-xl font-semibold text-white/85 sm:text-2xl"
              style={rise(isFaqVisible, "0.2s")}>
              {t("about:faq.headline")}
            </p>
          </div>

          <dl className="mt-10">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n, idx) => {
              const isOpen = openFaq === n;
              return (
                <div
                  key={n}
                  className="border-t border-white/8"
                  style={revealUp(isFaqVisible, `${0.08 + idx * 0.045}s`, "0.55s")}
                >
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpenFaq(isOpen ? null : n)}
                    className="group flex w-full items-start justify-between gap-4 py-5 text-start"
                  >
                    <dt className="text-sm font-medium leading-relaxed text-white/70 transition-colors duration-200 group-hover:text-white/90">
                      {t(`about:faq.q${n}`)}
                    </dt>
                    <span
                      className="mt-0.5 shrink-0 text-copper/60 transition-all duration-300 group-hover:text-copper"
                      style={{ transform: isOpen ? "rotate(45deg)" : "rotate(0deg)" }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
                        <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
                      </svg>
                    </span>
                  </button>
                  <dd
                    className="overflow-hidden text-sm leading-relaxed text-white/45"
                    style={{
                      maxHeight: isOpen ? "24rem" : "0",
                      opacity: isOpen ? 1 : 0,
                      paddingBottom: isOpen ? "1.25rem" : "0",
                      transition: isOpen
                        ? "max-height 0.38s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.28s ease, padding-bottom 0.3s ease"
                        : "max-height 0.08s ease, opacity 0.06s ease, padding-bottom 0.08s ease",
                    }}
                  >
                    {t(`about:faq.a${n}`)}
                  </dd>
                </div>
              );
            })}
            <div className="border-t border-white/8" />
          </dl>
        </div>
      </div>

      {/* ── CTA ──────────────────────────────────────────────────────────── */}
      <div className="texture-wave bg-void px-6 py-24 sm:py-32">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-[clamp(1.4rem,3.5vw,2.2rem)] font-light text-white/45">
            {t("about:hero.subtitle")}
          </p>
          <Link
            to="/contact"
            className="mt-10 inline-block rounded-sm bg-copper px-8 py-3 text-sm font-medium text-white transition-colors duration-300 hover:bg-gold"
          >
            {t("about:cta")}
          </Link>
        </div>
      </div>

    </div>
    </>
  );
}
