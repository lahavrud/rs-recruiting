import type { CSSProperties } from "react";

import { useTranslation } from "react-i18next";

import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";

const EMAIL = "support@rs-recruiting.com";

function rise(delay = "0s", duration = "0.85s"): CSSProperties {
  return { animation: `text-rise ${duration} cubic-bezier(0.16, 1, 0.3, 1) ${delay} both` };
}

function revealUp(delay = "0s"): CSSProperties {
  return { animation: `reveal-up 0.8s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both` };
}

function ruleDraw(delay = "0s"): CSSProperties {
  return {
    animation: `line-expand-h 0.75s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both`,
    transformOrigin: "right",
  };
}

export default function ContactPage() {
  const { t } = useTranslation('ui');

  return (
    <>
      <SeoHead
        title={t("ui:contact.seo.title")}
        description={t("ui:contact.seo.description")}
        canonical={`${SITE_URL}/contact`}
        ogImage={`${SITE_URL}/og/contact.svg`}
      />

      <div className="flex flex-1 flex-col bg-void">

      {/* ── Single hero section — fills remaining viewport height ────────── */}
      <section className="texture-wave relative flex flex-1 flex-col items-center justify-center overflow-hidden px-6 text-center">
        {/* Copper radial glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 60% at 50% 50%, color-mix(in srgb, var(--color-copper) 9%, transparent), transparent)",
          }}
        />

        <div className="relative mx-auto max-w-xl">
          {/* Eyebrow */}
          <div className="flex flex-col items-center gap-2">
            <div className="h-px w-10 bg-copper/50" style={ruleDraw("0.2s")} />
            <div className="overflow-hidden">
              <p
                className="text-xs font-semibold uppercase tracking-widest text-copper/75"
                style={rise("0.4s", "0.6s")}
              >
                {t("ui:contact.eyebrow")}
              </p>
            </div>
          </div>

          {/* Headline */}
          <div className="mt-8 overflow-hidden">
            <h1
              className="text-[clamp(2.8rem,8vw,5.5rem)] font-light leading-tight text-white/88"
              style={rise("0.55s", "0.9s")}
            >
              {t("ui:contact.headline")}
            </h1>
          </div>

          {/* Subtitle */}
          <p
            className="mx-auto mt-6 max-w-sm text-base leading-relaxed text-white/40"
            style={revealUp("0.9s")}
          >
            {t("ui:contact.subtitle")}
          </p>

          {/* Email */}
          <div className="mt-12 overflow-hidden">
            <a
              href={`mailto:${EMAIL}`}
              className="font-wordmark text-[clamp(1.1rem,3vw,1.6rem)] font-light tracking-wide text-copper/80 transition-colors duration-300 hover:text-gold"
              style={rise("1.05s")}
            >
              {EMAIL}
            </a>
          </div>

          {/* Decorative line */}
          <div
            className="mx-auto mt-8 h-px w-16 bg-copper/30"
            style={{
              animation: "line-expand-h 1s cubic-bezier(0.22, 1, 0.36, 1) 1.2s both",
              transformOrigin: "center",
            }}
          />
        </div>
      </section>

    </div>
    </>
  );
}
