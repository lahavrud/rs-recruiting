import { motion, useReducedMotion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import LandingEyebrow from "./LandingEyebrow";
import { staggerContainer, fadeRise, VIEWPORT_ONCE } from "./landingMotionUtils";

const SECTORS = [
  { titleKey: "landing:sectors.s1Title", subKey: "landing:sectors.s1Sub" },
  { titleKey: "landing:sectors.s2Title", subKey: "landing:sectors.s2Sub" },
  { titleKey: "landing:sectors.s3Title", subKey: "landing:sectors.s3Sub" },
] as const;

/* Specialization sectors: each one is a full-width row separated by
   hairlines, with an oversized title and a roles line. The whole row is
   the link. On hover the separator turns brass, the title shifts and
   turns gold, and the arrow steps in. */
export default function LandingSectors() {
  const { t } = useTranslation('landing');
  const reduceMotion = useReducedMotion();

  return (
    <section className="bg-void py-24 sm:py-32">
      <motion.div
        variants={staggerContainer}
        initial={reduceMotion ? false : "hidden"}
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        className="mx-auto max-w-7xl px-6 sm:px-12"
      >
        <LandingEyebrow>{t("landing:sectors.eyebrow")}</LandingEyebrow>
        <motion.h2
          variants={fadeRise}
          className="font-display mt-4 max-w-2xl text-3xl font-black leading-tight text-white/95 sm:text-5xl"
        >
          {t("landing:sectors.title")}
        </motion.h2>

        <motion.div variants={fadeRise} className="mt-16 border-t border-white/8 sm:mt-20">
          {SECTORS.map(({ titleKey, subKey }, i) => (
            <Link
              key={titleKey}
              to="/jobs"
              className="group relative flex flex-col gap-3 border-b border-white/8 py-9 sm:flex-row sm:items-center sm:gap-10 sm:py-12"
            >
              {/* Separator below the row, drawn in from the reading edge
                  on hover */}
              <span
                aria-hidden="true"
                className="brass-hairline absolute -bottom-px inset-x-0 h-px origin-right scale-x-0 transition-transform duration-700 ease-out group-hover:scale-x-100"
              />

              <span className="font-display text-sm font-medium tabular-nums text-copper/50 transition-colors duration-500 group-hover:text-copper sm:w-12 sm:shrink-0">
                {String(i + 1).padStart(2, "0")}
              </span>

              <h3 className="font-display text-3xl font-black leading-none text-white/90 transition-[color,padding] duration-500 group-hover:ps-2 group-hover:text-gold sm:flex-1 sm:text-5xl">
                {t(titleKey)}
              </h3>

              <p className="text-sm leading-relaxed text-white/40 transition-colors duration-500 group-hover:text-white/70 sm:max-w-sm sm:text-base md:max-w-md">
                {t(subKey)
                  .split(",")
                  .map((role) => role.trim())
                  .join(" · ")}
              </p>

              <span
                aria-hidden="true"
                className="hidden translate-x-2 text-2xl text-copper opacity-0 transition-all duration-500 group-hover:translate-x-0 group-hover:opacity-100 sm:block"
              >
                ←
              </span>
            </Link>
          ))}
        </motion.div>
      </motion.div>
    </section>
  );
}
