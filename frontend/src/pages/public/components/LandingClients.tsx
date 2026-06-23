import { useEffect, useRef, useState } from "react";

import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
} from "motion/react";
import { useTranslation } from "react-i18next";

import LandingEyebrow from "./LandingEyebrow";
import { fadeRise } from "./landingMotionUtils";

/* Client logo marquee: marks drift by in color; on hover or drag the
   track pauses and drops to mono.

   Color states (logos are dark marks on a dark theme):
   - "color": invert(1) hue-rotate(180deg) flips lightness but keeps the
     hue family, so dark-green CBRE reads as light green, navy stays blue.
     Elegance ships its own opaque ground and needs no lift.
   - "mono": white-silhouette treatment (brightness(0) invert(1));
     opaque-ground marks desaturate instead. */

const LIFT = "invert(1) hue-rotate(180deg)";
const SILHOUETTE = "brightness(0) invert(1)";
const DESATURATE = "grayscale(1) brightness(1.7)";

const CLIENTS = [
  { src: "/clients/cbre.png", alt: "CBRE", color: LIFT, mono: SILHOUETTE },
  { src: "/clients/hilla.png", alt: "Hilla Group", color: LIFT, mono: SILHOUETTE },
  { src: "/clients/yakir.png", alt: "יקיר ב. בע״מ", color: LIFT, mono: SILHOUETTE },
  { src: "/clients/erp-logic.png", alt: "ERP Logic", color: LIFT, mono: SILHOUETTE },
  { src: "/clients/menivim.png", alt: "מניבים - קרן הריט החדשה", color: LIFT, mono: SILHOUETTE },
  { src: "/clients/epstein.png", alt: "Epstein - ניהול פרויקטים", color: LIFT, mono: SILHOUETTE },
  { src: "/clients/elegance.png", alt: "Elegance", color: "none", mono: DESATURATE },
] as const;

const SPEED_PX_S = 28;
// Floor: two copies always suffice for a seamless loop on narrow viewports;
// the live measurement raises this when one copy can't fill the strip.
const MIN_COPIES = 2;

function wrap(min: number, max: number, v: number): number {
  const range = max - min;
  return ((((v - min) % range) + range) % range) + min;
}

export default function LandingClients() {
  const { t } = useTranslation('landing');
  const shouldReduceMotion = useReducedMotion();

  const [isHovering, setIsHovering] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const isPaused = isHovering || isDragging || Boolean(shouldReduceMotion);

  const viewportRef = useRef<HTMLDivElement>(null);
  const setRef = useRef<HTMLDivElement>(null);
  const setWidth = useRef(0);
  const x = useMotionValue(0);

  // One copy of the logos is narrower than a wide viewport, so two copies
  // can't fill the strip — once the first scrolls off there's nothing on the
  // right and a blank gap opens before the loop. Render as many copies as it
  // takes to overfill the viewport plus one spare to scroll in, re-measuring
  // whenever the viewport or the (dvh-sized) logos resize.
  const [copies, setCopies] = useState(MIN_COPIES);

  useEffect(() => {
    const measure = () => {
      const set = setRef.current;
      const viewport = viewportRef.current;
      if (!set || !viewport) return;
      const w = set.offsetWidth;
      if (!w) return;
      setWidth.current = w;
      setCopies(Math.max(MIN_COPIES, Math.ceil(viewport.offsetWidth / w) + 1));
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (viewportRef.current) observer.observe(viewportRef.current);
    if (setRef.current) observer.observe(setRef.current);
    return () => observer.disconnect();
  }, []);

  // Drift left by exactly one copy's width, then wrap — the spare copies keep
  // the strip filled across the seam.
  useAnimationFrame((_, delta) => {
    const w = setWidth.current;
    if (!w) return;
    const current = x.get();
    if (!isPaused) {
      x.set(wrap(-w, 0, current - (SPEED_PX_S * delta) / 1000));
    } else if (current < -w || current > 0) {
      // While dragging, only step in to re-wrap at the loop seam.
      x.set(wrap(-w, 0, current));
    }
  });

  return (
    /* A slim ribbon along the hero's bottom edge. The lighter section tone
       fills only the content column (between the container guides); the top
       and bottom hairlines run the full width, so outside the column the
       ground stays void. */
    <section className="shrink-0 border-y border-white/8">
      <motion.div
        variants={fadeRise}
        initial={shouldReduceMotion ? false : "hidden"}
        whileInView="visible"
        viewport={{ once: true, amount: 0.4 }}
        className="mx-auto max-w-7xl bg-section px-6 py-[clamp(0.5rem,2dvh,1.25rem)] sm:px-12"
      >
        <LandingEyebrow className="text-center">
          {t("landing:clients.eyebrow")}
        </LandingEyebrow>

        <div
          ref={viewportRef}
          dir="ltr"
          className="mt-[clamp(0.25rem,1.5dvh,0.75rem)] overflow-hidden"
          style={{
            maskImage:
              "linear-gradient(to right, transparent, black 12%, black 88%, transparent)",
            WebkitMaskImage:
              "linear-gradient(to right, transparent, black 12%, black 88%, transparent)",
          }}
          onPointerEnter={() => setIsHovering(true)}
          onPointerLeave={() => setIsHovering(false)}
        >
          <motion.div
            drag="x"
            dragMomentum={false}
            onDragStart={() => setIsDragging(true)}
            onDragEnd={() => setIsDragging(false)}
            style={{ x }}
            className={`flex w-max cursor-grab items-center active:cursor-grabbing ${
              isPaused ? "marquee-paused" : ""
            }`}
          >
            {Array.from({ length: copies }, (_, copy) => (
              <div
                key={copy}
                ref={copy === 0 ? setRef : undefined}
                aria-hidden={copy !== 0}
                className="flex shrink-0 items-center"
              >
                {CLIENTS.map(({ src, alt, color, mono }) => (
                  <img
                    key={`${copy}-${src}`}
                    src={src}
                    alt={alt}
                    // Eager fetch + async decode: lazy loading made off-screen
                    // logos pop in at the loop seam, while sync decode froze
                    // the marquee's rAF loop on the big marks. The mount-time
                    // decode() below primes every logo so neither happens.
                    loading="eager"
                    decoding="async"
                    draggable={false}
                    className="client-logo mx-6 size-[clamp(2.5rem,6dvh,4rem)] select-none object-contain sm:mx-10"
                    style={
                      {
                        "--logo-color": color,
                        "--logo-mono": mono,
                      } as React.CSSProperties
                    }
                  />
                ))}
              </div>
            ))}
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}
