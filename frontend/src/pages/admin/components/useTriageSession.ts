import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { updateApplicationStatus } from "@/services/adminApplications";
import { ApplicationStatus } from "@/types/enums";

import { type Decision } from "./triageTypes";
import { type TriageItem } from "./useTriageQueue";

interface DecisionEntry {
  decision: Decision;
  prevIndex: number;
}

/** localStorage key for the once-per-user swipe hint dismissal. */
const SWIPE_HINT_KEY = "triage.swipeHintSeen";

const SWIPE_TRIGGER = 80;
const SLIDE_MS = 240;

interface UseTriageSessionArgs {
  items: TriageItem[];
  /** Whether the resume modal is currently open — gates decision/nav keys. */
  isResumeOpen: boolean;
  onCloseResume: () => void;
  onExit: () => void;
  toast: { error: (msg: string) => void };
  t: (key: string, opts?: Record<string, unknown>) => string;
}

/**
 * Owns the triage carousel (swipe/drag/slide animation), the decide/undo
 * state machine, and the keyboard shortcut wiring — everything that drives
 * the interactive session once the queue of candidates is loaded. The page
 * still owns the queue fetch itself (`useTriageQueue`) and the resume-modal
 * visibility flag, since both are needed by render gates before this hook's
 * state becomes meaningful.
 */
export function useTriageSession({
  items,
  isResumeOpen,
  onCloseResume,
  onExit,
  toast,
  t,
}: UseTriageSessionArgs) {
  const [index, setIndex] = useState(0);
  const [decisions, setDecisions] = useState<Record<number, DecisionEntry>>({});
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [pendingUndo, setPendingUndo] = useState<{
    appId: number;
    decision: Decision;
    prevIndex: number;
  } | null>(null);

  const current = items[index] ?? null;
  const total = items.length;
  const prevApp = index > 0 ? items[index - 1] : null;
  const nextApp = index < total - 1 ? items[index + 1] : null;
  const decidedCount = useMemo(() => Object.keys(decisions).length, [decisions]);

  // ── Carousel: real screen-switching animation ───────────────────────
  // Layout: three cards rendered side-by-side in a flex row (DOM order
  // [next, current, prev]). In RTL flex `next` sits on the visual right —
  // same side the LTR strip shows it. Swipe-left pushes the current card
  // away and the next card slides in from the right (iOS Photos pattern).
  //
  //   default (showing current):   translateX( 100vw )
  //   showing next  (swipe left):  translateX(   0vw )
  //   showing prev  (swipe right): translateX( 200vw )
  //
  // After the slide animation finishes we increment `index` AND reset
  // translateX to 100vw inside an `isSwapping` window so the user sees no
  // jump — the candidate that was at the "next" slot is now the "current"
  // slot, at the same physical position.
  const [dragX, setDragX] = useState(0);
  const [flying, setFlying] = useState<"next" | "prev" | null>(null);
  const [isSwapping, setIsSwapping] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  // Persist hint-seen so it shows once per user, not once per session
  const carouselRef = useRef<HTMLDivElement>(null);
  const [isHintSeen, setIsHintSeenRaw] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SWIPE_HINT_KEY) === "1";
    } catch {
      return false;
    }
  });
  const setIsHintSeen = useCallback((seen: boolean) => {
    setIsHintSeenRaw(seen);
    if (seen) {
      try {
        localStorage.setItem(SWIPE_HINT_KEY, "1");
      } catch {
        // Storage might be blocked (private mode, full quota). Silent fallback.
      }
    }
  }, []);
  const touchStart = useRef<{
    x: number;
    y: number;
    axis: "h" | "v" | null;
  } | null>(null);

  const slideTo = useCallback(
    (dir: "next" | "prev") => {
      if (flying || isSwapping) return;
      if (dir === "next" && index >= total - 1) return;
      if (dir === "prev" && index <= 0) return;
      setFlying(dir);
    },
    [flying, isSwapping, index, total],
  );

  const goNext = useCallback(() => slideTo("next"), [slideTo]);
  const goPrev = useCallback(() => slideTo("prev"), [slideTo]);

  /**
   * Navigate to a specific candidate by index. Used by the strip's chip-jump
   * (skips animation since the destination may be many steps away — animating
   * a multi-step jump looks wrong).
   */
  const jumpTo = useCallback(
    (newIndex: number) => {
      if (newIndex === index) return;
      setIndex(newIndex);
    },
    [index],
  );

  const decide = useCallback(
    (decision: Decision) => {
      if (!current) return;
      if (flying || isSwapping) return; // guard against keyboard spam mid-flight
      const appId = current.id;
      const prevIndex = index;

      // Optimistic local update + advance
      setDecisions((prev) => ({ ...prev, [appId]: { decision, prevIndex } }));
      setPendingUndo({ appId, decision, prevIndex });
      goNext();

      // Persist in background; on failure, roll local back and tell the user.
      updateApplicationStatus(appId, { status: decision }).catch(() => {
        setDecisions((prev) => {
          const next = { ...prev };
          delete next[appId];
          return next;
        });
        setPendingUndo((p) => (p?.appId === appId ? null : p));
        toast.error(t("admin:applications.triage.errors.saveDecision"));
      });
    },
    [current, flying, isSwapping, goNext, index, toast, t],
  );

  /**
   * Retract a decision and restore the candidate to NEW server-side. Used by
   * both the UndoToast (immediate retraction post-decide) and the RevisitBanner
   * (retraction after navigating away from a decided card).
   */
  const retractDecision = useCallback(
    (appId: number, jumpBack: number | null) => {
      // Snapshot for rollback if the server rejects the revert
      const snapshot = decisions[appId];
      setDecisions((prev) => {
        const next = { ...prev };
        delete next[appId];
        return next;
      });
      setPendingUndo((p) => (p?.appId === appId ? null : p));
      if (jumpBack != null) setIndex(jumpBack);

      updateApplicationStatus(appId, { status: ApplicationStatus.NEW }).catch(() => {
        if (snapshot) {
          setDecisions((prev) => ({ ...prev, [appId]: snapshot }));
        }
        toast.error(t("admin:applications.triage.errors.undoDecision"));
      });
    },
    [decisions, toast, t],
  );

  const undo = useCallback(() => {
    if (!pendingUndo) return;
    retractDecision(pendingUndo.appId, pendingUndo.prevIndex);
  }, [pendingUndo, retractDecision]);

  const clearDecisionFor = useCallback(
    (appId: number) => retractDecision(appId, null),
    [retractDecision],
  );

  /** Build the per-candidate strip items in submission order */
  const stripItems = useMemo(
    () =>
      items.map((app, i) => ({
        id: app.id,
        index: i,
        decision: decisions[app.id]?.decision ?? null,
      })),
    [items, decisions],
  );

  // Drive the flying animation: kick off the transform, then on completion
  // swap the index and reset transform inside an `isSwapping` window that
  // disables the transition so the snap-back is invisible.
  //
  // We listen for `transitionend` on the carousel wrapper for accurate timing
  // (CSS transitions can be throttled in background tabs or under load, so a
  // bare setTimeout would misfire). A safety timeout fires if the event never
  // arrives — guards against edge cases like tab visibility changes mid-slide.
  useEffect(() => {
    if (!flying) return;
    const el = carouselRef.current;
    if (!el) return;

    let done = false;
    const commit = () => {
      if (done) return;
      done = true;
      setIsSwapping(true);
      if (flying === "next") setIndex((i) => Math.min(i + 1, total - 1));
      else setIndex((i) => Math.max(i - 1, 0));
      setFlying(null);
      setDragX(0);
      // Two rAFs ensure the browser paints the reset state with transition
      // disabled before we re-enable transitions.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => setIsSwapping(false)),
      );
    };

    const onEnd = (e: TransitionEvent) => {
      if (e.target !== el || e.propertyName !== "transform") return;
      commit();
    };

    el.addEventListener("transitionend", onEnd);
    const fallback = setTimeout(commit, SLIDE_MS + 80);

    return () => {
      el.removeEventListener("transitionend", onEnd);
      clearTimeout(fallback);
    };
  }, [flying, total]);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (window.innerWidth >= 1024) return;
      if (flying || isSwapping) return;
      const targetEl = e.target as HTMLElement | null;
      if (targetEl?.closest("textarea, button, a, input, [contenteditable]")) return;
      const touch = e.touches[0];
      touchStart.current = { x: touch.clientX, y: touch.clientY, axis: null };
      setIsDragging(true);
    },
    [flying, isSwapping],
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!touchStart.current) return;
      const touch = e.touches[0];
      const dx = touch.clientX - touchStart.current.x;
      const dy = touch.clientY - touchStart.current.y;
      if (touchStart.current.axis === null && Math.hypot(dx, dy) > 10) {
        touchStart.current.axis = Math.abs(dy) > Math.abs(dx) ? "v" : "h";
      }
      if (touchStart.current.axis === "v") return;
      if (touchStart.current.axis === "h") {
        // Clamp at edges: don't drag past the first/last with no neighbor.
        // A small rubber-band gives tactile feedback that you've hit a bound.
        // iOS-style: left-swipe goes next, right-swipe goes prev.
        let clamped = dx;
        if (dx < 0 && !nextApp) clamped = Math.max(dx * 0.3, -40);
        else if (dx > 0 && !prevApp) clamped = Math.min(dx * 0.3, 40);
        setDragX(clamped);
        setIsHintSeen(true);
      }
    },
    [prevApp, nextApp, setIsHintSeen],
  );

  const onTouchEnd = useCallback(() => {
    setIsDragging(false);
    if (!touchStart.current) {
      setDragX(0);
      return;
    }
    const axis = touchStart.current.axis;
    touchStart.current = null;
    if (axis !== "h") {
      setDragX(0);
      return;
    }
    // iOS Photos convention: swipe left pushes current away and reveals the
    // next card from the right. Matches the visual physics of "card moves
    // with finger, new content fills the empty space behind."
    if (dragX < -SWIPE_TRIGGER && nextApp) {
      setFlying("next");
    } else if (dragX > SWIPE_TRIGGER && prevApp) {
      setFlying("prev");
    } else {
      setDragX(0);
    }
  }, [dragX, nextApp, prevApp]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const isTyping =
        target?.tagName === "TEXTAREA" || target?.tagName === "INPUT";
      if (isTyping) {
        if (e.key === "Escape") (target as HTMLElement).blur();
        return;
      }
      if (e.key === "Escape") {
        if (isResumeOpen) onCloseResume();
        else onExit();
        return;
      }
      // When the resume modal is open, only Esc (handled above) and ? matter.
      // Decisions and nav should not fire underneath an open modal.
      if (isResumeOpen) {
        if (e.key !== "?") return;
      }
      if (e.key === "?") {
        setIsHelpOpen((s) => !s);
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "a") {
        e.preventDefault();
        decide("APPROVED_BY_ADMIN");
      } else if (k === "r") {
        e.preventDefault();
        decide("REJECTED");
      } else if (k === "z" && pendingUndo) {
        e.preventDefault();
        undo();
      } else if (k === "n" || e.key === "ArrowRight") {
        // LTR-style: ArrowRight = next (matches strip order 1→6 left-to-right)
        e.preventDefault();
        goNext();
      } else if (k === "p" || e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, goNext, goPrev, onExit, onCloseResume, undo, pendingUndo, isResumeOpen]);

  return {
    index,
    current,
    total,
    prevApp,
    nextApp,
    decisions,
    decidedCount,
    pendingUndo,
    setPendingUndo,
    stripItems,
    isHelpOpen,
    setIsHelpOpen,
    jumpTo,
    goNext,
    goPrev,
    decide,
    undo,
    clearDecisionFor,
    // Carousel mechanics — consumed directly by the page's JSX
    carouselRef,
    dragX,
    flying,
    isSwapping,
    isDragging,
    isHintSeen,
    setIsHintSeen,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    SLIDE_MS,
  };
}
