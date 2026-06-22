import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import AutoGrowTextarea from "@/components/ui/AutoGrowTextarea";
import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import { textareaCls } from "@/styles/forms";
import { DECISION_META, UNDECIDED_CHIP_BG, type Decision } from "./triageTypes";
import { IconArrowRight, IconCheck, IconClose } from "./TriageIcons";

/** Resolves a Decision's icon key to the actual SVG component. */
function DecisionIcon({
  decision,
  className,
}: {
  decision: Decision;
  className?: string;
}) {
  const Cmp = DECISION_META[decision].icon === "check" ? IconCheck : IconClose;
  return <Cmp className={className} />;
}

// ── Session status strip — per-candidate decision overview ──────────────
// Renders one small chip per candidate, color-coded by session decision.
// Clickable to jump. Scrolls horizontally if the queue is long.

interface StripItem {
  id: number;
  index: number;
  decision: Decision | null;
}

export function SessionStatusStrip({
  items,
  currentIndex,
  onJump,
}: {
  items: StripItem[];
  currentIndex: number;
  onJump: (index: number) => void;
}) {
  const { t } = useTranslation('admin');
  const activeChipRef = useRef<HTMLButtonElement>(null);

  // Keep the active chip centered when the user navigates. Without this,
  // long queues leave the active chip off-screen behind the overflow edge.
  useEffect(() => {
    activeChipRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [currentIndex]);

  return (
    <div className="relative shrink-0 border-b border-white/8 bg-void/40">
      {/* Edge fade gradients — signal that more chips exist off-screen.
          pointer-events-none so they don't block chip clicks at the edges. */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-8 bg-gradient-to-r from-void/80 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-8 bg-gradient-to-l from-void/80 to-transparent" />

      <div className="overflow-x-auto px-3 py-2 sm:px-6 sm:py-2.5">
        {/* `dir="ltr"` so chip #1 sits on the visual left and the latest chip on the right —
            gives a clear left-to-right timeline regardless of the page's RTL body.
            `mx-auto w-max` centers the row when it fits, allows overflow scroll when it doesn't. */}
        <div
          dir="ltr"
          className="mx-auto flex w-max items-center gap-1.5 sm:gap-2"
        >
          {items.map((item) => {
            const isCurrent = item.index === currentIndex;
            const meta = item.decision ? DECISION_META[item.decision] : null;
            return (
              <button
                key={item.id}
                ref={isCurrent ? activeChipRef : undefined}
                type="button"
                onClick={() => onJump(item.index)}
                aria-label={
                  meta
                    ? t("admin:applications.triage.candidateAriaWithStatus", {
                        num: item.index + 1,
                        status: t(meta.shortLabelKey),
                      })
                    : t("admin:applications.triage.candidateAria", { num: item.index + 1 })
                }
                aria-current={isCurrent ? "true" : undefined}
                className={`group relative inline-flex shrink-0 items-center justify-center rounded-md transition ${
                  isCurrent ? "size-7 ring-2 ring-copper ring-offset-2 ring-offset-void" : "size-6"
                } ${meta ? meta.chip : UNDECIDED_CHIP_BG}`}
              >
                {item.decision ? (
                  <DecisionIcon
                    decision={item.decision}
                    className={`size-3.5 ${meta?.text ?? ""}`}
                  />
                ) : (
                  <span className="text-[10px] font-medium tabular-nums text-white/35">
                    {item.index + 1}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Revisit banner — appears on already-decided candidates ─────────────

export function RevisitBanner({
  decision,
  onUndo,
}: {
  decision: Decision;
  onUndo: () => void;
}) {
  const { t } = useTranslation('admin');
  const meta = DECISION_META[decision];
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-md border ${meta.border} ${meta.bgTint} px-4 py-2.5`}
    >
      <div className={`flex items-center gap-2 text-sm ${meta.text}`}>
        <DecisionIcon decision={decision} className="size-4" />
        <span>{t(meta.bannerLabelKey)}</span>
      </div>
      <button
        type="button"
        onClick={onUndo}
        className="rounded-full bg-white/8 px-3 py-1 text-xs font-medium text-copper transition hover:bg-white/12 hover:text-gold"
      >
        {t("admin:applications.triage.undoBannerButton")}
      </button>
    </div>
  );
}

// ── Shared: auto-dismiss via timeout ─────────────────────────────────────

function useAutoDismiss(onDismiss: () => void, delayMs: number) {
  useEffect(() => {
    const id = setTimeout(onDismiss, delayMs);
    return () => clearTimeout(id);
  }, [onDismiss, delayMs]);
}

// ── Subtle swipe hint — once, then dismisses ──────────────────────────────

/**
 * Subtle swipe hint. Renders absolutely-positioned at the bottom of its
 * `relative` parent, so it sticks just above the action footer regardless
 * of viewport / safe-area changes.
 */
export function SwipeHint({ onDismiss }: { onDismiss: () => void }) {
  const { t } = useTranslation('admin');
  useAutoDismiss(onDismiss, 3500);
  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-full z-40 mb-2 flex justify-center px-4 lg:hidden"
      style={{ animation: "triage-hint-fade 3500ms ease-out forwards" }}
    >
      <div className="rounded-full border border-white/10 bg-card-raised/90 px-3.5 py-1.5 text-[11px] text-white/55 shadow-lg backdrop-blur">
        {t("admin:applications.triage.swipeHint")}
      </div>
    </div>
  );
}

// ── Answer block — minimal, no eyebrow noise ──────────────────────────────

export function AnswerBlock({
  label,
  body,
  compact = false,
}: {
  label: string;
  body: string;
  compact?: boolean;
}) {
  return (
    <div>
      <p className="mb-1.5 text-xs text-white/35">{label}</p>
      <p
        className={`whitespace-pre-wrap text-white/85 ${compact ? "text-sm" : "text-[15px] leading-relaxed"}`}
      >
        {body}
      </p>
    </div>
  );
}

// ── Decision buttons — the primary action group in the footer ────────────
// Two decisive choices, no opt-out. Users who want to defer just navigate
// past the candidate without deciding (arrows / swipe / strip jump).

export function DecisionButtons({
  onReject,
  onApprove,
}: {
  onReject: () => void;
  onApprove: () => void;
}) {
  const { t } = useTranslation('admin');
  return (
    <div className="flex flex-1 items-center justify-end gap-2 lg:flex-initial lg:justify-center lg:gap-3">
      <Button
        variant="danger"
        onClick={onReject}
        className="flex-1 sm:flex-initial lg:min-w-36 lg:px-7 lg:py-2.5 lg:text-base"
      >
        <IconClose className="me-2 hidden size-4 lg:inline-block" />
        {t("admin:applications.triage.decisionRejectButton")}
      </Button>
      <Button
        variant="success"
        onClick={onApprove}
        className="flex-1 sm:flex-initial lg:min-w-36 lg:px-7 lg:py-2.5 lg:text-base"
      >
        <IconCheck className="me-2 hidden size-4 lg:inline-block" />
        {t("admin:applications.triage.decisionApproveButton")}
      </Button>
    </div>
  );
}

// ── Side arrow — large edge-of-screen pager (desktop only) ───────────────

export function SideArrow({
  side,
  onClick,
  disabled,
  label,
}: {
  side: "left" | "right";
  onClick: () => void;
  disabled: boolean;
  label: string;
}) {
  const isLeft = side === "left";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`absolute inset-y-0 z-30 hidden w-14 items-center justify-center text-white/30 transition hover:bg-white/[0.04] hover:text-white/80 disabled:pointer-events-none disabled:opacity-25 lg:flex ${
        isLeft ? "left-0" : "right-0"
      }`}
    >
      <IconArrowRight className={`size-7 ${isLeft ? "-scale-x-100" : ""}`} />
    </button>
  );
}


// ── Note field — keyed reset per candidate ────────────────────────────────

export function NoteField({ initial }: { initial: string }) {
  const { t } = useTranslation('admin');
  const [value, setValue] = useState(initial);
  return (
    <AutoGrowTextarea
      value={value}
      onChange={setValue}
      minRows={2}
      placeholder={t("admin:applications.triage.notePlaceholder")}
      className={textareaCls}
    />
  );
}

// ── Undo toast — replaces the flashy decision overlay ─────────────────────

export function UndoToast({
  decision,
  onUndo,
  onDismiss,
}: {
  decision: Decision;
  onUndo: () => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation('admin');
  useAutoDismiss(onDismiss, 5000);

  const meta = DECISION_META[decision];
  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-full z-40 mb-2 flex justify-center px-4"
      style={{ animation: "triage-toast-in 200ms ease-out" }}
    >
      <div
        className={`pointer-events-auto inline-flex items-center gap-3 rounded-full border ${meta.border} bg-card-raised/95 py-2 ps-4 pe-1.5 text-sm text-white/85 shadow-lg backdrop-blur`}
      >
        <span>{t(meta.bannerLabelKey)}</span>
        <button
          type="button"
          onClick={onUndo}
          className="rounded-full bg-white/8 px-3 py-1 text-xs font-medium text-copper transition hover:bg-white/12 hover:text-gold"
        >
          {t("admin:applications.triage.undoButton")}
        </button>
      </div>
    </div>
  );
}

// ── Help overlay ──────────────────────────────────────────────────────────

export function HelpOverlay({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('admin');
  const rows: [string, string][] = [
    ["A", t("admin:applications.triage.help.approveAction")],
    ["R", t("admin:applications.triage.help.rejectAction")],
    ["N  /  →", t("admin:applications.triage.help.nextAction")],
    ["P  /  ←", t("admin:applications.triage.help.prevAction")],
    ["Z", t("admin:applications.triage.help.undoLastAction")],
    ["Esc", t("admin:applications.triage.help.exitAction")],
    ["?", t("admin:applications.triage.help.toggleHelpAction")],
  ];
  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={t("admin:applications.triage.help.title")}
      size="sm"
    >
      <ul className="space-y-2 text-sm text-white/80">
        {rows.map(([key, desc]) => (
          <li
            key={key}
            className="flex items-center justify-between border-b border-white/5 pb-1.5"
          >
            <span>{desc}</span>
            <kbd className="rounded border border-white/15 bg-white/5 px-2 py-0.5 text-xs text-white/60">
              {key}
            </kbd>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}

// ── End-of-queue summary ──────────────────────────────────────────────────

export function SummaryScreen({
  decisions,
  onExit,
}: {
  decisions: Record<number, Decision>;
  onExit: () => void;
}) {
  const { t } = useTranslation('admin');
  const counts = Object.values(decisions).reduce(
    (acc, d) => {
      acc[d] = (acc[d] ?? 0) + 1;
      return acc;
    },
    {} as Record<Decision, number>,
  );
  // Order matters for visual layout: approvals first, rejections second.
  const decisionsInOrder: Decision[] = ["APPROVED_BY_ADMIN", "REJECTED"];

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-page px-6 text-white"
      dir="rtl"
    >
      <div className="w-full max-w-lg rounded-md border border-white/10 bg-card-raised p-6 text-center sm:p-8">
        <p className="text-[11px] uppercase tracking-widest text-white/40">
          {t("admin:applications.triage.summaryEyebrow")}
        </p>
        <h1 className="mt-3 text-xl font-light sm:text-2xl">
          {t("admin:applications.triage.summaryTitle")}
        </h1>
        <p className="mt-1 text-sm text-white/50">
          {t("admin:applications.triage.summarySubtitle")}
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3">
          {decisionsInOrder.map((d) => {
            const meta = DECISION_META[d];
            return (
              <div
                key={d}
                className="rounded-md border border-white/8 bg-card/50 px-3 py-4"
              >
                <p className={`text-3xl font-light tabular-nums ${meta.text}`}>
                  {counts[d] ?? 0}
                </p>
                <p className="mt-1 text-[11px] uppercase tracking-widest text-white/40">
                  {t(meta.summaryLabelKey)}
                </p>
              </div>
            );
          })}
        </div>

        <div className="mt-8 flex flex-col items-center justify-center gap-2 sm:flex-row">
          <Button
            variant="ghost"
            onClick={() => window.location.reload()}
            className="w-full sm:w-auto"
          >
            {t("admin:applications.triage.startNewReview")}
          </Button>
          <Button onClick={onExit} className="w-full sm:w-auto">
            {t("admin:applications.triage.backToList")}
          </Button>
        </div>
      </div>
    </div>
  );
}
