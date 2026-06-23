import { useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import { ResumeViewer } from "@/components/ui/ResumeViewer";
import { useToast } from "@/hooks/useToast";

import { CandidateCard } from "./components/TriageCandidateCard";
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
import { useTriageQueue, type TriageItem } from "./components/useTriageQueue";
import { useTriageSession } from "./components/useTriageSession";

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
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const toast = useToast();
  const { items, isLoading, error, reload } = useTriageQueue();
  const [isResumeOpen, setIsResumeOpen] = useState(false);

  const {
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
  } = useTriageSession({
    items,
    isResumeOpen,
    onCloseResume: () => setIsResumeOpen(false),
    onExit: () => navigate("/admin/applications"),
    toast,
    t,
  });

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

  const areAllDecided = decidedCount === total && !pendingUndo;
  if (areAllDecided) {
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
          <span className="hidden sm:inline">
            {t("admin:applications.triage.exit")}
          </span>
        </button>

        {/* Absolute-centered title — fills the header, pointer-events-none
            so it doesn't intercept clicks meant for the side buttons. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
          <p className="max-w-full truncate text-sm text-white/85 tabular-nums">
            {t("admin:applications.triage.progress", {
              current: index + 1,
              total,
            })}
            <span className="hidden text-white/40 sm:inline">
              {" "}
              · {current.job.title}
            </span>
          </p>
          {decidedCount > 0 && (
            <p className="mt-0.5 text-[11px] text-white/40">
              {t("admin:applications.triage.decidedCount", { count: decidedCount })}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsHelpOpen((s) => !s)}
          className="relative z-10 hidden shrink-0 rounded-sm border border-white/10 px-2.5 py-1.5 text-xs text-white/45 transition hover:border-copper/40 hover:text-white sm:inline-flex"
          aria-label={t("admin:applications.triage.keyboardShortcutsAria")}
        >
          <kbd className="text-[11px]">?</kbd>
        </button>
      </header>

      {/* ── Session status strip — one chip per candidate ──────────────── */}
      <SessionStatusStrip items={stripItems} currentIndex={index} onJump={jumpTo} />

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
              isSwapping || isDragging ? "none" : `transform ${SLIDE_MS}ms ease-out`,
          }}
        >
          {/* DOM order: next, current, prev — in RTL flex this places next on
              the visual right and prev on the visual left. iOS Photos pattern:
              swipe LEFT to push current away, next slides in from the right. */}
          <CarouselSlot app={nextApp}>
            {nextApp && (
              <CandidateCard
                app={nextApp}
                isActive={false}
                decision={decisions[nextApp.id]?.decision ?? null}
                onOpenResume={() => setIsResumeOpen(true)}
                onUndoDecision={() => clearDecisionFor(nextApp.id)}
              />
            )}
          </CarouselSlot>

          <CarouselSlot app={current}>
            <CandidateCard
              app={current}
              isActive
              decision={decisions[current.id]?.decision ?? null}
              onOpenResume={() => setIsResumeOpen(true)}
              onUndoDecision={() => clearDecisionFor(current.id)}
            />
          </CarouselSlot>

          <CarouselSlot app={prevApp}>
            {prevApp && (
              <CandidateCard
                app={prevApp}
                isActive={false}
                decision={decisions[prevApp.id]?.decision ?? null}
                onOpenResume={() => setIsResumeOpen(true)}
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
        {!isHintSeen && index === 0 && <SwipeHint onDismiss={() => setIsHintSeen(true)} />}

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
      {isHelpOpen && <HelpOverlay onClose={() => setIsHelpOpen(false)} />}
      {isResumeOpen && current.candidate.resume_path && (
        <ResumeViewer
          candidateName={current.candidate.full_name}
          resumePath={current.candidate.resume_path}
          onClose={() => setIsResumeOpen(false)}
        />
      )}
    </div>
  );
}
