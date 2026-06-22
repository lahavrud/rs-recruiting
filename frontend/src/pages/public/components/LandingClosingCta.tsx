import { motion, useReducedMotion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { staggerContainer, fadeRise, VIEWPORT_ONCE } from "./landingMotionUtils";

/* Closing CTA: heading on the start side, the two actions on the end
   side, one secondary line underneath. */
export default function LandingClosingCta() {
  const { t } = useTranslation('landing');
  const reduceMotion = useReducedMotion();

  return (
    <section className="relative bg-section">
      <div className="brass-hairline absolute inset-x-0 top-0 h-px opacity-50" />

      <motion.div
        variants={staggerContainer}
        initial={reduceMotion ? false : "hidden"}
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        className="mx-auto max-w-7xl px-6 py-28 sm:px-12 sm:py-36"
      >
        <div className="grid items-center gap-12 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <motion.h2
              variants={fadeRise}
              className="font-display text-4xl font-black leading-tight tracking-tight text-white/95 sm:text-6xl"
            >
              {t("landing:closing.title")}
            </motion.h2>
            <motion.p
              variants={fadeRise}
              className="mt-5 max-w-md text-base font-light leading-relaxed text-white/50 sm:text-lg"
            >
              {t("landing:closing.subtitle")}
            </motion.p>
          </div>

          <motion.div
            variants={fadeRise}
            className="flex flex-wrap gap-4 lg:col-span-5 lg:justify-end"
          >
            <Link
              to="/jobs"
              className="font-display block bg-copper px-12 py-4 text-base font-bold text-white shadow-lg transition-colors duration-300 hover:bg-gold"
            >
              {t("landing:closing.ctaJobs")}
            </Link>
            <Link
              to="/contact"
              className="font-display block border border-white/15 px-12 py-4 text-base font-bold text-white/70 transition-colors duration-300 hover:border-copper/50 hover:text-white"
            >
              {t("landing:closing.ctaContact")}
            </Link>
          </motion.div>
        </div>

        <motion.p variants={fadeRise} className="mt-16 text-sm text-white/35">
          {t("landing:closing.companiesNote")}{" "}
          <Link
            to="/contact"
            className="text-copper underline decoration-copper/30 underline-offset-4 transition-colors hover:text-gold"
          >
            {t("landing:closing.companiesLink")}
          </Link>
        </motion.p>
      </motion.div>
    </section>
  );
}
