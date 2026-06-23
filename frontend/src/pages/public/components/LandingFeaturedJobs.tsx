import { useEffect, useMemo, useRef, useState } from "react";

import { motion, useReducedMotion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Button from "@/components/ui/Button";
import type { JobPublicRead } from "@/types/jobs";
import { formatSalary } from "@/utils/salary";

import LandingEyebrow from "./LandingEyebrow";
import {
  staggerContainer,
  fadeRise,
  VIEWPORT_ONCE,
  EASE_OUT,
} from "./landingMotionUtils";

const MAX_CARDS = 5;
const MAX_VISIBLE_DEPTH = 3;
const AUTO_ADVANCE_MS = 5000;
const DRAG_THRESHOLD_PX = 60;
const SHUFFLE_S = 0.55;

/** Resting transform for a card sitting `depth` cards behind the front. */
function stackPose(depth: number, isHidden: boolean) {
  return {
    x: depth * -14,
    y: depth * -18,
    scale: 1 - depth * 0.05,
    opacity: isHidden ? 0 : 1 - depth * 0.28,
  };
}

/* Single job card: location eyebrow, index numeral, title, description,
   and a footer rule with the salary in gold. */
function JobCard({ job, order }: { job: JobPublicRead; order: number }) {
  const { t } = useTranslation(["landing", "common"]);
  const salary = formatSalary(job.salary_min, job.salary_max);

  return (
    <Link
      to={`/jobs/${job.id}`}
      draggable={false}
      className="group relative flex h-full flex-col border border-white/10 bg-card p-7 shadow-2xl transition-colors duration-300 hover:border-copper/40 sm:p-9"
    >
      <div className="brass-hairline absolute inset-x-0 top-0 h-px opacity-60 transition-opacity duration-500 group-hover:opacity-100" />

      <div className="flex items-baseline justify-between gap-4">
        <p className="text-[11px] font-medium tracking-widest text-copper">
          {job.location}
          {job.tags.length > 0 && ` · ${job.tags[0]}`}
        </p>
        <span className="font-display text-sm font-bold tabular-nums text-white/20">
          {String(order + 1).padStart(2, "0")}
        </span>
      </div>

      <h3 className="font-display mt-5 line-clamp-2 text-2xl font-black leading-tight text-white/95 sm:text-3xl">
        {job.title}
      </h3>
      <p className="mt-4 line-clamp-3 text-sm font-light leading-relaxed text-white/50 sm:text-base">
        {job.short_description}
      </p>

      <div className="mt-auto pt-8">
        <div className="mb-5 h-px bg-white/8" />
        <div className="flex items-end justify-between gap-4">
          {salary ? (
            <div>
              <p className="text-[10px] font-medium tracking-widest text-white/30">
                {t("common:salary")}
              </p>
              <p className="font-display mt-1 text-lg font-bold tabular-nums text-gold">
                {salary}
              </p>
            </div>
          ) : (
            <span />
          )}
          <span className="text-sm font-medium text-copper transition-colors duration-300 group-hover:text-gold">
            {t("landing:featuredJobs.view")} ←
          </span>
        </div>
      </div>
    </Link>
  );
}

/* Featured jobs: a text column beside a card deck. The deck auto-advances
   every few seconds; the front card can be dragged away or stepped with
   the arrows. Each card simply tweens to its new resting pose — the front
   card dissolves back into the stack while the next one settles forward. */
export default function LandingFeaturedJobs({
  jobs,
  isLoading,
}: {
  jobs: JobPublicRead[];
  isLoading: boolean;
}) {
  const { t } = useTranslation(["landing"]);
  const shouldReduceMotion = useReducedMotion();

  const featuredJobs = useMemo(
    () => jobs.filter((j) => j.is_featured).slice(0, MAX_CARDS),
    [jobs],
  );
  const count = featuredJobs.length;

  const [index, setIndex] = useState(0);
  const [isHovering, setIsHovering] = useState(false);
  // Swallows the click that follows a drag so the card doesn't navigate.
  const draggedRef = useRef(false);

  const next = () => setIndex((i) => (i + 1) % count);
  const prev = () => setIndex((i) => (i - 1 + count) % count);

  useEffect(() => {
    if (shouldReduceMotion || isHovering || count < 2) return;
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % count);
    }, AUTO_ADVANCE_MS);
    return () => clearInterval(id);
    // `index` restarts the timer after manual navigation.
  }, [shouldReduceMotion, isHovering, count, index]);

  if (isLoading || count === 0) return null;

  return (
    <section className="border-y border-white/6 bg-section py-24 sm:py-32">
      <motion.div
        variants={staggerContainer}
        initial={shouldReduceMotion ? false : "hidden"}
        whileInView="visible"
        viewport={VIEWPORT_ONCE}
        className="mx-auto grid max-w-7xl items-center gap-16 px-6 sm:px-12 lg:grid-cols-2 lg:gap-20"
      >
        {/* Text column */}
        <div>
          <LandingEyebrow>{t("landing:featuredJobs.eyebrow")}</LandingEyebrow>
          <motion.h2
            variants={fadeRise}
            className="font-display mt-4 text-3xl font-black leading-tight text-white/95 sm:text-5xl"
          >
            {t("landing:featuredJobs.title")}
          </motion.h2>
          <motion.p
            variants={fadeRise}
            className="mt-5 max-w-md text-base font-light leading-relaxed text-white/50 sm:text-lg"
          >
            {t("landing:featuredJobs.subtitle")}
          </motion.p>
          <motion.div variants={fadeRise}>
            <Link
              to="/jobs"
              className="mt-8 inline-block text-sm font-medium text-copper transition-colors hover:text-gold"
            >
              {t("landing:featuredJobs.viewAll")} ←
            </Link>
          </motion.div>

          {count > 1 && (
            <motion.div variants={fadeRise} className="mt-12 flex items-center gap-5">
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={t("landing:featuredJobs.prev")}
                  onClick={prev}
                >
                  →
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={t("landing:featuredJobs.next")}
                  onClick={next}
                >
                  ←
                </Button>
              </div>
              <span
                dir="ltr"
                className="font-display text-sm tabular-nums text-white/40"
              >
                {String(index + 1).padStart(2, "0")} / {String(count).padStart(2, "0")}
              </span>
              <div className="h-px flex-1 bg-white/10">
                <motion.div
                  className="brass-hairline h-full origin-right"
                  animate={{ scaleX: (index + 1) / count }}
                  transition={{ duration: 0.5, ease: EASE_OUT }}
                />
              </div>
            </motion.div>
          )}
        </div>

        {/* The deck */}
        <motion.div
          variants={fadeRise}
          className="relative h-[26rem] sm:h-[27rem]"
          onPointerEnter={() => setIsHovering(true)}
          onPointerLeave={() => setIsHovering(false)}
        >
          {featuredJobs.map((job, i) => {
            const depth = (i - index + count) % count;
            const isFront = depth === 0;
            const isHidden = depth >= MAX_VISIBLE_DEPTH;

            return (
              <motion.div
                key={job.id}
                className="absolute inset-0"
                style={{
                  zIndex: count - depth,
                  pointerEvents: isFront ? "auto" : "none",
                }}
                animate={stackPose(depth, isHidden)}
                transition={{ duration: shouldReduceMotion ? 0 : SHUFFLE_S, ease: EASE_OUT }}
                drag={isFront && count > 1 ? "x" : false}
                dragConstraints={{ left: 0, right: 0 }}
                dragElastic={0.4}
                dragMomentum={false}
                onDragStart={() => {
                  draggedRef.current = true;
                }}
                onDragEnd={(_, info) => {
                  setTimeout(() => {
                    draggedRef.current = false;
                  }, 0);
                  if (info.offset.x < -DRAG_THRESHOLD_PX) next();
                  else if (info.offset.x > DRAG_THRESHOLD_PX) prev();
                }}
                onClickCapture={(e) => {
                  if (draggedRef.current) e.preventDefault();
                }}
              >
                <JobCard job={job} order={i} />
              </motion.div>
            );
          })}
        </motion.div>
      </motion.div>
    </section>
  );
}
