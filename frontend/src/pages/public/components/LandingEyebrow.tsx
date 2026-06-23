import type { ReactNode } from "react";

import { motion } from "motion/react";

import { fadeRise } from "./landingMotionUtils";

/* Shared "copper caps label" eyebrow for the landing redesign — distinct
   from the app-wide <Eyebrow> (10px uppercase). Participates in the
   parent's stagger/variant tree via `variants={fadeRise}`. */
export default function LandingEyebrow({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.p
      variants={fadeRise}
      className={`text-xs font-medium tracking-widest text-copper ${className}`.trim()}
    >
      {children}
    </motion.p>
  );
}
