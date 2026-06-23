import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "motion/react";

import { createSilkRenderer, readSilkPalette } from "./landingSilkUtils";

/* Silk backdrop for the hero's start-side void: a WebGL canvas of molten
   silk bands (plum → wine → copper → gold) flowing from under the navbar
   down to the client-logo ribbon, which cuts it. Decorative only — hidden
   from AT, no pointer targets. Desktop gets the full pour beside the copy;
   below lg it stays as a subtle ambient wash behind it.

   Degradation ladder: animated WebGL → static frame (reduced motion) →
   CSS gradient wash (no WebGL2). */

/** Tailwind `lg` (64rem) — full intensity above, ambient wash below. */
const DESKTOP_QUERY = "(min-width: 64rem)";
/** Fragment work scales with dpr²; 2 is indistinguishable from native 3. */
const DESKTOP_DPR_CAP = 2;
const MOBILE_DPR_CAP = 1.5;
/** Mobile sits directly behind the copy, so it only whispers —
    any brighter and the headline loses contrast. */
const MOBILE_GAIN = 0.16;
/** Per-frame pointer easing — heavy, liquid lag behind the cursor. */
const POINTER_EASE = 0.045;
/** Entrance fade, paced with the hero copy reveal. */
const FADE_DURATION_S = 1.6;
/** Frozen timestamp for the reduced-motion still — a flattering pose. */
const STATIC_TIME_S = 23;

export default function LandingSilk() {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reduceMotion = useReducedMotion();

  const [isDesktop, setIsDesktop] = useState(
    () => window.matchMedia(DESKTOP_QUERY).matches,
  );
  // Read inside the render effect without making it a dependency — toggling
  // this shouldn't tear down and recreate the WebGL context (disposing then
  // re-`getContext`ing the same canvas leaves it permanently lost).
  const isDesktopRef = useRef(isDesktop);
  const refitRef = useRef<() => void>(() => {});

  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_QUERY);
    const onChange = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    isDesktopRef.current = isDesktop;
    refitRef.current();
  }, [isDesktop]);

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    if (!host || !canvas) return;

    let renderer = createSilkRenderer(canvas, readSilkPalette());
    if (!renderer) {
      // No WebGL2 — leave the CSS gradient wash underneath visible.
      canvas.style.display = "none";
      return;
    }

    let raf = 0;
    let running = false;
    let intersecting = false;
    let started: number | null = null;
    let pointerX = 0;
    let pointerY = 0;
    let targetX = 0;
    let targetY = 0;
    // Last drawn frame, so a resize can repaint synchronously (see fit()).
    let lastTime = reduceMotion ? STATIC_TIME_S : 0;
    let lastFade = reduceMotion ? 1 : 0;

    const drawFrame = () => {
      const gain = isDesktopRef.current ? 1 : MOBILE_GAIN;
      renderer?.draw(lastTime, pointerX, pointerY, lastFade * gain);
    };

    const frame = (now: DOMHighResTimeStamp) => {
      raf = requestAnimationFrame(frame);
      if (started === null) started = now;
      const t = (now - started) / 1000;
      const linear = Math.min(1, t / FADE_DURATION_S);
      lastTime = t;
      lastFade = 1 - (1 - linear) ** 3;
      pointerX += (targetX - pointerX) * POINTER_EASE;
      pointerY += (targetY - pointerY) * POINTER_EASE;
      drawFrame();
    };
    const start = () => {
      if (!running) {
        running = true;
        raf = requestAnimationFrame(frame);
      }
    };
    const stop = () => {
      if (running) {
        running = false;
        cancelAnimationFrame(raf);
      }
    };

    const fit = () => {
      const cap = isDesktopRef.current ? DESKTOP_DPR_CAP : MOBILE_DPR_CAP;
      const dpr = Math.min(window.devicePixelRatio || 1, cap);
      renderer?.resize(host.clientWidth, host.clientHeight, dpr);
      // Resizing clears the buffer to black; repaint now rather than letting
      // a black box show until the next rAF tick (visible when maximizing).
      drawFrame();
    };
    refitRef.current = fit;
    fit();
    // A live drag-resize fires the observer on every pixel — coalesce to
    // one resize per frame so the GL drawing buffer isn't reallocated fast
    // enough to exhaust the GPU and lose the context.
    let fitRaf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(fitRaf);
      fitRaf = requestAnimationFrame(fit);
    });
    ro.observe(host);

    // GPU processes get suspended (and lose their WebGL context) when the
    // window is minimized; the browser fires `webglcontextrestored` once
    // it's back, but the old GL resources are gone — rebuild the renderer.
    // Shared between the reduced-motion and animated paths so a context loss
    // while reduced motion is active still falls back to the CSS wash and
    // recovers (redrawing the static frame) on restore.
    const onContextLost = (e: Event) => {
      e.preventDefault();
      stop();
      canvas.style.display = "none";
    };
    const onContextRestored = () => {
      renderer?.dispose();
      renderer = createSilkRenderer(canvas, readSilkPalette());
      if (!renderer) {
        return;
      }
      canvas.style.display = "";
      fit();
      if (reduceMotion) return;
      if (intersecting) start();
    };
    canvas.addEventListener("webglcontextlost", onContextLost);
    canvas.addEventListener("webglcontextrestored", onContextRestored);

    if (reduceMotion) {
      return () => {
        refitRef.current = () => {};
        cancelAnimationFrame(fitRaf);
        ro.disconnect();
        canvas.removeEventListener("webglcontextlost", onContextLost);
        canvas.removeEventListener("webglcontextrestored", onContextRestored);
        renderer?.dispose();
      };
    }

    // Parallax follows the cursor anywhere on the page — the silk is an
    // ambient layer, not a hover target.
    const onPointerMove = (e: PointerEvent) => {
      targetX = (e.clientX / window.innerWidth) * 2 - 1;
      targetY = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });

    // Only burn GPU while the hero is actually on screen.
    const io = new IntersectionObserver(([entry]) => {
      intersecting = entry?.isIntersecting ?? false;
      if (intersecting) start();
      else stop();
    });
    io.observe(host);

    return () => {
      refitRef.current = () => {};
      stop();
      cancelAnimationFrame(fitRaf);
      io.disconnect();
      ro.disconnect();
      window.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      canvas.removeEventListener("webglcontextrestored", onContextRestored);
      renderer?.dispose();
    };
  }, [reduceMotion]);

  return (
    /* Stage rides the content column (same pattern as the page's guide
       hairlines), inset 1px so the guides stay visible as cutting edges.
       The negative bottom extends through the hero's reserved spacer — both
       read the shared --landing-ribbon-gap custom property (index.css) —
       so the canvas's bottom edge lands exactly on the client ribbon, which
       cuts the silk. */
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-px top-0 -bottom-[var(--landing-ribbon-gap)] mx-auto max-w-7xl"
    >
      {/* end-0 = the visual left in RTL: the void beside the hero copy. */}
      <div
        ref={hostRef}
        className={`absolute inset-y-0 end-0 ${isDesktop ? "w-[min(58%,46rem)]" : "w-full"}`}
      >
        {/* Static wash, visible only when WebGL2 is unavailable. */}
        <div className="absolute inset-0 [background:radial-gradient(110%_70%_at_30%_60%,color-mix(in_srgb,var(--color-wine)_16%,transparent),transparent_70%),radial-gradient(70%_55%_at_42%_24%,color-mix(in_srgb,var(--color-copper)_12%,transparent),transparent_72%)]" />
        <canvas ref={canvasRef} className="absolute inset-0 size-full" />
      </div>
    </div>
  );
}
