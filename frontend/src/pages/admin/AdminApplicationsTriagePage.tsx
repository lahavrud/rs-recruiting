import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import Button from "@/components/ui/Button";
import { useToast } from "@/hooks/useToast";
import { updateApplicationStatus } from "@/services/adminApplications";
import { ApplicationStatus } from "@/types/api";
import { ResumeViewer } from "@/components/ui/ResumeViewer";
import {
  DecisionButtons,
  HelpOverlay,
  SessionStatusStrip,
  SideArrow,
  SummaryScreen,
  SwipeHint,
  UndoToast,
} from "./components/TriageComponents";
import { IconClose } from "./components/TriageIcons";
import { CandidateCard } from "./components/TriageCandidateCard";
import { type Decision } from "./components/triageTypes";
import { useTriageQueue, type TriageItem } from "./components/useTriageQueue";

/**
 * Full-screen centered status panel — used for loading / empty / error states
 * before the carousel can render.
 */
function CenteredMessage({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-page px-6 text-center text-white/75"
      dir="rtl"
    >
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}

/** Single slot in the carousel — always full viewport width, even when empty. */
function CarouselSlot({
  app,
  children,
}: {
  app: TriageItem | null;
  children: React.ReactNode;
}) {
  return (
    <div
      className="relative h-full w-full shrink-0"
      style={{ width: "100vw" }}
      aria-hidden={!app}
    >
      {children}
    </div>
  );
}

interface DecisionEntry {
  decision: Decision;
  prevIndex: number;
}

/** localStorage key for the once-per-user swipe hint dismissal. */
const SWIPE_HINT_KEY = "triage.swipeHintSeen";

/**
 * Triage mode — fullscreen, keyboard-first application reviewer.
 *
 * UX principles:
 *   - Decisions are deliberate (button + keyboard), never gestural.
 *   - Swipe is for navigation only — flipping through candidates like a stack.
 *   - Every decision is undo-able for 5 seconds.
 *   - Resume opens on demand (modal), not always-on.
 *   - Minimal chrome: labels recede, content leads.
 */
export default function AdminApplicationsTriagePage() {
  const { t } = useTranslation('admin');
  const navigate = useNavigate();
  const toast = useToast();
  const { items, isLoading, error, reload } = useTriageQueue();
  const [index, setIndex] = useState(0);
  const [decisions, setDecisions] = useState<Record<number, DecisionEntry>>({});
  const [showHelp, setShowHelp] = useState(false);
  const [showResume, setShowResume] = useState(false);
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
  const SWIPE_TRIGGER = 80;
  const SLIDE_MS = 240;
  const [dragX, setDragX] = useState(0);
  const [flying, setFlying] = useState<"next" | "prev" | null>(null);
  const [isSwapping, setIsSwapping] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  // Persist hint-seen so it shows once per user, not once per session
  const carouselRef = useRef<HTMLDivElement>(null);
  const [hintSeen, setHintSeenRaw] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SWIPE_HINT_KEY) === "1";
    } catch {
      return false;
    }
  });
  const setHintSeen = useCallback((seen: boolean) => {
    setHintSeenRaw(seen);
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
      const t = e.target as HTMLElement | null;
      if (t?.closest("textarea, button, a, input, [contenteditable]")) return;
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
        setHintSeen(true);
      }
    },
    [prevApp, nextApp, setHintSeen],
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
        if (showResume) setShowResume(false);
        else navigate("/admin/applications");
        return;
      }
      // When the resume modal is open, only Esc (handled above) and ? matter.
      // Decisions and nav should not fire underneath an open modal.
      if (showResume) {
        if (e.key !== "?") return;
      }
      if (e.key === "?") {
        setShowHelp((s) => !s);
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
  }, [decide, goNext, goPrev, navigate, undo, pendingUndo, showResume]);

  // ── Render gates: loading / error / empty / done ──────────────────────
  if (isLoading) {
    return <CenteredMessage>{t("admin:applications.triage.loading")}</CenteredMessage>;
  }
  if (error) {
    return (
      <CenteredMessage>
        <p>{t("admin:applications.triage.errorTitle")}</p>
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="ghost" onClick={() => navigate("/admin/applications")}>
            {t("admin:applications.triage.back")}
          </Button>
          <Button onClick={reload}>{t("admin:applications.triage.retry")}</Button>
        </div>
      </CenteredMessage>
    );
  }
  if (total === 0) {
    return (
      <CenteredMessage>
        <p>{t("admin:applications.triage.emptyTitle")}</p>
        <p className="mt-1 text-sm text-white/40">
          {t("admin:applications.triage.emptySubtitle")}
        </p>
        <div className="mt-6 flex justify-center">
          <Button onClick={() => navigate("/admin/applications")}>
            {t("admin:applications.triage.backToList")}
          </Button>
        </div>
      </CenteredMessage>
    );
  }

  const allDecided = decidedCount === total && !pendingUndo;
  if (allDecided) {
    return (
      <SummaryScreen
        decisions={Object.fromEntries(
          Object.entries(decisions).map(([k, v]) => [k, v.decision]),
        )}
        onExit={() => navigate("/admin/applications")}
      />
    );
  }

  if (!current) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-page text-white" dir="rtl">
      {/* ── Top bar — minimal: exit + contextual progress + help ─────────
            Title is absolutely-centered so it sits at the viewport's true
            center regardless of the exit/help button widths. */}
      <header className="relative flex shrink-0 items-center justify-between border-b border-white/8 bg-void/80 px-3 py-2.5 backdrop-blur sm:px-6 sm:py-3">
        <button
          type="button"
          onClick={() => navigate("/admin/applications")}
          className="relative z-10 inline-flex shrink-0 items-center gap-2 rounded-sm border border-white/10 px-2 py-1.5 text-xs text-white/55 transition hover:border-white/30 hover:text-white sm:px-3"
          aria-label={t("admin:applications.triage.exitAria")}
        >
          <IconClose />
          <span className="hidden sm:inline">{t("admin:applications.triage.exit")}</span>
        </button>

        {/* Absolute-centered title — fills the header, pointer-events-none
            so it doesn't intercept clicks meant for the side buttons. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
          <p className="max-w-full truncate text-sm text-white/85 tabular-nums">
            {t("admin:applications.triage.progress", {
              current: index + 1,
              total,
            })}
            <span className="hidden text-white/40 sm:inline"> · {current.job.title}</span>
          </p>
          {decidedCount > 0 && (
            <p className="mt-0.5 text-[11px] text-white/40">
              {t("admin:applications.triage.decidedCount", { count: decidedCount })}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => setShowHelp((s) => !s)}
          className="relative z-10 hidden shrink-0 rounded-sm border border-white/10 px-2.5 py-1.5 text-xs text-white/45 transition hover:border-copper/40 hover:text-white sm:inline-flex"
          aria-label={t("admin:applications.triage.keyboardShortcutsAria")}
        >
          <kbd className="text-[11px]">?</kbd>
        </button>
      </header>

      {/* ── Session status strip — one chip per candidate ──────────────── */}
      <SessionStatusStrip
        items={stripItems}
        currentIndex={index}
        onJump={jumpTo}
      />

      {/* ── Body — single column, generous breathing room ──────────────── */}
      <div
        className="relative flex min-h-0 flex-1 overflow-hidden"
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onTouchCancel={onTouchEnd}
      >
        {/* Carousel wrapper — slides between prev/current/next */}
        <div
          ref={carouselRef}
          className="absolute inset-0 flex"
          style={{
            transform:
              flying === "next"
                ? "translateX(0vw)"
                : flying === "prev"
                  ? "translateX(200vw)"
                  : `translateX(calc(100vw + ${dragX}px))`,
            transition:
              isSwapping || isDragging
                ? "none"
                : `transform ${SLIDE_MS}ms ease-out`,
          }}
        >
          {/* DOM order: next, current, prev — in RTL flex this places next on
              the visual right and prev on the visual left. iOS Photos pattern:
              swipe LEFT to push current away, next slides in from the right. */}
          <CarouselSlot app={nextApp}>
            {nextApp && (
              <CandidateCard
                app={nextApp}
                active={false}
                decision={decisions[nextApp.id]?.decision ?? null}
                onOpenResume={() => setShowResume(true)}
                onUndoDecision={() => clearDecisionFor(nextApp.id)}
              />
            )}
          </CarouselSlot>

          <CarouselSlot app={current}>
            <CandidateCard
              app={current}
              active
              decision={decisions[current.id]?.decision ?? null}
              onOpenResume={() => setShowResume(true)}
              onUndoDecision={() => clearDecisionFor(current.id)}
            />
          </CarouselSlot>

          <CarouselSlot app={prevApp}>
            {prevApp && (
              <CandidateCard
                app={prevApp}
                active={false}
                decision={decisions[prevApp.id]?.decision ?? null}
                onOpenResume={() => setShowResume(true)}
                onUndoDecision={() => clearDecisionFor(prevApp.id)}
              />
            )}
          </CarouselSlot>
        </div>

        {/* Desktop side arrows. Direction matches the LTR status strip
            (chips go 1→6 left-to-right) so right = forward, left = back. */}
        <SideArrow
          side="right"
          onClick={goNext}
          disabled={index === total - 1}
          label={t("admin:applications.triage.nextCandidate")}
        />
        <SideArrow
          side="left"
          onClick={goPrev}
          disabled={index === 0}
          label={t("admin:applications.triage.prevCandidate")}
        />
      </div>

      {/* ── Action bar ─────────────────────────────────────────────────
            Mobile/tablet: nav arrows + 3 buttons (split layout).
            Desktop (lg+): no nav (side arrows handle it), centered larger
            decision buttons with icons for accessibility. */}
      <footer
        className="relative shrink-0 border-t border-white/8 bg-void/80 px-3 py-3 backdrop-blur sm:px-6"
        style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
      >
        {/* Pills are children of the footer so they anchor to its top edge
            via `bottom-full`. Always sit just above the action buttons,
            independent of safe-area or scrollable card content. */}
        {pendingUndo && (
          <UndoToast
            decision={pendingUndo.decision}
            onUndo={undo}
            onDismiss={() => setPendingUndo(null)}
          />
        )}
        {!hintSeen && index === 0 && (
          <SwipeHint onDismiss={() => setHintSeen(true)} />
        )}

        <div className="mx-auto flex max-w-3xl items-center justify-center gap-3 lg:gap-4">
          {/* Mobile: swipe navigates. Desktop: side arrows + keyboard. No
              dedicated nav buttons in the footer — decisions get all the room. */}
          <DecisionButtons
            onReject={() => decide("REJECTED")}
            onApprove={() => decide("APPROVED_BY_ADMIN")}
          />
        </div>
      </footer>

      {/* ── True overlays (modals — top-level so they cover the whole page) */}
      {showHelp && <HelpOverlay onClose={() => setShowHelp(false)} />}
      {showResume && current.candidate.resume_path && (
        <ResumeViewer
          candidateName={current.candidate.full_name}
          resumePath={current.candidate.resume_path}
          onClose={() => setShowResume(false)}
        />
      )}
    </div>
  );
}
