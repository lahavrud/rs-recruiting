import { useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import { useTranslation } from "react-i18next";

import RangeSlider from "@/components/ui/RangeSlider";
import { JobStatus } from "@/types/enums";
const ALL_STATUSES = [
  JobStatus.PENDING_APPROVAL,
  JobStatus.PUBLISHED,
  JobStatus.CLOSED,
];

const SALARY_FORM_MIN = 0;
const SALARY_FORM_MAX = 40000;
const SALARY_FORM_STEP = 500;
const SALARY_SPAN = SALARY_FORM_MAX - SALARY_FORM_MIN;

export { default as Field } from "@/components/ui/Field";

/** Featured-toggle as a star button. Click opens a confirm dialog in the parent. */
export function FeaturedStarButton({
  isActive,
  onToggleRequest,
}: {
  isActive: boolean;
  onToggleRequest: () => void;
}) {
  const { t } = useTranslation(["admin", "common"]);
  return (
    <button
      type="button"
      onClick={onToggleRequest}
      aria-pressed={isActive}
      aria-label={t("admin:jobs.fields.featuredToggleAria")}
      title={t(isActive ? "admin:jobs.featuredOnHint" : "admin:jobs.featuredOffHint")}
      className={`inline-flex size-10 shrink-0 items-center justify-center rounded-sm border transition duration-200 active:scale-90 ${
        isActive
          ? "border-gold/60 bg-gold/15 text-gold hover:bg-gold/25"
          : "border-white/15 text-white/40 hover:border-gold/40 hover:text-gold/80"
      }`}
    >
      <svg
        viewBox="0 0 24 24"
        fill={isActive ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        className="size-5"
        aria-hidden="true"
      >
        <path d="M12 2.5l3.09 6.26 6.91 1.01-5 4.87 1.18 6.88L12 18.27l-6.18 3.25L7 14.64 2 9.77l6.91-1.01L12 2.5z" />
      </svg>
    </button>
  );
}

type SegmentConfig = { sliderCls: string; activeCls: string; dotCls: string };

const STATUS_SEGMENT_CONFIG: Record<JobStatus, SegmentConfig> = {
  [JobStatus.PENDING_APPROVAL]: {
    sliderCls: "bg-warning/10 border-warning/25",
    activeCls: "text-warning",
    dotCls: "bg-warning/65",
  },
  [JobStatus.PUBLISHED]: {
    sliderCls: "bg-success/10 border-success/25",
    activeCls: "text-success",
    dotCls: "bg-success/65",
  },
  [JobStatus.CLOSED]: {
    sliderCls: "bg-white/7 border-white/18",
    activeCls: "text-white/70",
    dotCls: "bg-white/40",
  },
};

/** Status as a segmented control — sliding highlight encodes selection independent of color. */
export function StatusPills({
  value,
  onChange,
}: {
  value: JobStatus;
  onChange: (s: JobStatus) => void;
}) {
  const { t } = useTranslation(["admin", "common"]);
  const activeIdx = ALL_STATUSES.indexOf(value);
  const cfg = STATUS_SEGMENT_CONFIG[value];

  return (
    <div
      role="radiogroup"
      aria-label={t("admin:jobs.fields.status")}
      className="relative mt-1 flex overflow-hidden rounded-lg border border-white/10 bg-well"
    >
      {/* Sliding highlight — tracks active segment with a smooth lateral animation */}
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-[3px] rounded-md border ${cfg.sliderCls}`}
        style={{
          width: `calc(100% / ${ALL_STATUSES.length})`,
          insetInlineStart: `calc(${activeIdx} * 100% / ${ALL_STATUSES.length})`,
          transition:
            "inset-inline-start 220ms cubic-bezier(0.4, 0, 0.2, 1), background-color 180ms ease, border-color 180ms ease",
        }}
      />

      {ALL_STATUSES.map((s) => {
        const isActive = value === s;
        const c = STATUS_SEGMENT_CONFIG[s];
        return (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(s)}
            className={`relative z-10 flex flex-1 items-center justify-center gap-1.5 py-2 text-xs font-medium transition-colors duration-200 ${
              isActive ? c.activeCls : "text-white/38 hover:text-white/60"
            }`}
          >
            {/* Status dot — scales in when segment activates */}
            <span
              aria-hidden="true"
              className={`size-1.5 shrink-0 rounded-full transition-[opacity,transform] duration-200 ${c.dotCls} ${
                isActive ? "scale-100 opacity-100" : "scale-0 opacity-0"
              }`}
            />
            {t(`admin:jobs.statusLabels.${s}`)}
          </button>
        );
      })}
    </div>
  );
}

const RADIX = 10;
// Approximate half-width of a salary bubble (₪ + 6ch input + padding + border ≈ 80 px).
// Used to keep bubbles within the slider's bounds even at extreme thumb positions.
const BUBBLE_HALF_WIDTH_PX = 40;
// Minimum physical gap (px) between two bubble edges before push-apart kicks in.
const MIN_INTER_BUBBLE_GAP_PX = 8;
// Vertical distance (px) from the bubble-container's bottom edge to the
// large thumb's vertical centre: (-mt-1 = 4 px overlap) + (size-7 / 2 = 14 px) = 10 px.
// Fallback minimum gap % used before the first ResizeObserver measurement fires.
const MIN_GAP_PCT_FALLBACK = 16;
const CARET_REACH_PX = 18;
// Half-height of the SVG arrowhead polygon.
const ARROWHEAD_H = 4;

// Editable bubble pinned above a range-slider thumb.
// • insetInlineStart + translateX(50%) centres it horizontally over the thumb.
// • caretOffsetPx is the physical-pixel horizontal distance from this bubble's
//   display centre to the actual thumb centre (negative = thumb is to the left).
//   The SVG caret angles to bridge the gap so the arrow always points at the thumb.
interface SalaryBubbleProps {
  value: number;
  draft: string | null;
  pct: number;
  caretOffsetPx: number;
  ariaLabel: string;
  onFocus: () => void;
  onChange: (v: string) => void;
  onBlur: () => void;
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
}

function SalaryBubble({
  value,
  draft,
  pct,
  caretOffsetPx,
  ariaLabel,
  onFocus,
  onChange,
  onBlur,
  onKeyDown,
}: SalaryBubbleProps) {
  const tipX = caretOffsetPx;
  const tipY = CARET_REACH_PX;
  return (
    <div
      className="absolute bottom-0 flex flex-col items-center"
      style={{ insetInlineStart: `${pct}%`, transform: "translateX(50%)" }}
    >
      <div className="inline-flex items-center gap-0.5 rounded border border-copper/30 bg-card px-2 py-1 text-sm shadow-sm shadow-black/40">
        <span className="shrink-0 text-white/35" aria-hidden="true">
          ₪
        </span>
        <input
          type="text"
          inputMode="numeric"
          value={draft ?? value.toLocaleString("he-IL")}
          onFocus={onFocus}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          onKeyDown={onKeyDown}
          aria-label={ariaLabel}
          className="w-[6ch] bg-transparent text-center text-copper/90 outline-none"
        />
      </div>
      {/* SVG caret: height=0 so it doesn't shift the bubble; overflow:visible
          lets the line+arrowhead extend into the slider area below. When
          caretOffsetPx≠0 (push-apart active) the line angles toward the thumb. */}
      <svg
        aria-hidden="true"
        className="pointer-events-none overflow-visible"
        style={{ width: "1px", height: "0px" }}
      >
        <line
          x1={0}
          y1={0}
          x2={tipX}
          y2={tipY}
          stroke="rgba(184,115,51,0.3)"
          strokeWidth="1"
        />
        <polygon
          points={`${tipX - 3},${tipY - ARROWHEAD_H} ${tipX + 3},${tipY - ARROWHEAD_H} ${tipX},${tipY}`}
          fill="rgba(184,115,51,0.3)"
        />
      </svg>
    </div>
  );
}

export function SalaryRangeField({
  min,
  max,
  onChange,
  error,
}: {
  min?: number;
  max?: number;
  onChange: (lo: number, hi: number) => void;
  error?: string;
}) {
  const { t } = useTranslation(["admin", "common"]);

  // Must be declared before any computation that uses containerWidth.
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      setContainerWidth(entries[0].contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const lo = Math.max(
    SALARY_FORM_MIN,
    Math.min(min ?? SALARY_FORM_MIN, SALARY_FORM_MAX),
  );
  const hi = Math.max(
    Math.min(SALARY_FORM_MAX, Math.max(max ?? SALARY_FORM_MAX, SALARY_FORM_MIN)),
    lo,
  );

  // null = showing locale-formatted value; non-null = user is actively typing
  const [draftLo, setDraftLo] = useState<string | null>(null);
  const [draftHi, setDraftHi] = useState<string | null>(null);

  const span = SALARY_SPAN || 1;
  const loPct = ((lo - SALARY_FORM_MIN) / span) * 100;
  const hiPct = ((hi - SALARY_FORM_MIN) / span) * 100;

  // Edge padding: keeps bubbles within the slider's bounds at extreme positions.
  // When a thumb is near 0 % or 100 %, translateX(50 %) would push half the
  // bubble outside the container; clamping prevents that. The caret then angles
  // to show where the thumb actually is (same mechanism as collision avoidance).
  const edgePadPct =
    containerWidth > 0 ? (BUBBLE_HALF_WIDTH_PX / containerWidth) * 100 : 0;
  const clampToBounds = (pct: number) =>
    Math.max(edgePadPct, Math.min(100 - edgePadPct, pct));

  // Dynamic minimum gap: both bubble widths + a small visual gutter, in percent.
  const minGapPct =
    containerWidth > 0
      ? ((BUBBLE_HALF_WIDTH_PX * 2 + MIN_INTER_BUBBLE_GAP_PX) / containerWidth) * 100
      : MIN_GAP_PCT_FALLBACK;

  // Push bubbles apart when they'd collide; carets still point to the right thumb.
  const rawGap = hiPct - loPct;
  const half = minGapPct / 2;
  const mid = (loPct + hiPct) / 2;
  const displayLoPct = clampToBounds(rawGap < minGapPct ? mid - half : loPct);
  const displayHiPct = clampToBounds(rawGap < minGapPct ? mid + half : hiPct);

  const commitLo = () => {
    if (draftLo === null) return;
    const n = parseInt(draftLo, RADIX);
    onChange(
      isNaN(n) ? lo : Math.max(SALARY_FORM_MIN, Math.min(n, hi - SALARY_FORM_STEP)),
      hi,
    );
    setDraftLo(null);
  };

  const commitHi = () => {
    if (draftHi === null) return;
    const n = parseInt(draftHi, RADIX);
    onChange(
      lo,
      isNaN(n) ? hi : Math.max(lo + SALARY_FORM_STEP, Math.min(n, SALARY_FORM_MAX)),
    );
    setDraftHi(null);
  };

  // Physical-pixel offset of each thumb from its pushed bubble centre.
  // (displayPct - actualPct) / 100 * containerWidth gives the RTL-aware
  // signed distance: negative means the thumb is to the left of the bubble.
  const loCaretOffsetPx = ((displayLoPct - loPct) / 100) * containerWidth;
  const hiCaretOffsetPx = ((displayHiPct - hiPct) / 100) * containerWidth;

  const inputBoxCls =
    "flex items-center gap-1 rounded-md border border-copper/30 bg-card px-2.5 py-2 text-sm shadow-sm shadow-black/40 focus-within:border-copper/60";

  return (
    <div className="mt-1">
      {/* Mobile (< sm): two labeled inputs side by side.
          Floating bubbles don't work on narrow screens — this gives precise entry
          and clear visual feedback without overflow/collision issues. */}
      <div className="mb-3 grid grid-cols-2 gap-2 sm:hidden">
        <div>
          <p className="mb-1 text-[10px] text-white/40">{t("common:salaryMin")}</p>
          <div className={inputBoxCls}>
            <span className="shrink-0 text-white/35" aria-hidden="true">
              ₪
            </span>
            <input
              type="text"
              inputMode="numeric"
              value={draftLo ?? lo.toLocaleString("he-IL")}
              onFocus={() => {
                if (draftLo === null) setDraftLo(String(lo));
              }}
              onChange={(e) => setDraftLo(e.target.value)}
              onBlur={commitLo}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commitLo();
                }
                if (e.key === "Escape") setDraftLo(null);
              }}
              aria-label={t("common:salaryMin")}
              className="min-w-0 flex-1 bg-transparent text-center text-copper/90 outline-none"
            />
          </div>
        </div>
        <div>
          <p className="mb-1 text-[10px] text-white/40">{t("common:salaryMax")}</p>
          <div className={inputBoxCls}>
            <span className="shrink-0 text-white/35" aria-hidden="true">
              ₪
            </span>
            <input
              type="text"
              inputMode="numeric"
              value={draftHi ?? hi.toLocaleString("he-IL")}
              onFocus={() => {
                if (draftHi === null) setDraftHi(String(hi));
              }}
              onChange={(e) => setDraftHi(e.target.value)}
              onBlur={commitHi}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commitHi();
                }
                if (e.key === "Escape") setDraftHi(null);
              }}
              aria-label={t("common:salaryMax")}
              className="min-w-0 flex-1 bg-transparent text-center text-copper/90 outline-none"
            />
          </div>
        </div>
      </div>

      {/* Desktop (≥ sm): floating bubbles above slider */}
      <div ref={containerRef}>
        <div className="relative hidden h-10 overflow-visible sm:block">
          <SalaryBubble
            value={lo}
            draft={draftLo}
            pct={displayLoPct}
            caretOffsetPx={loCaretOffsetPx}
            ariaLabel={t("common:salaryMin")}
            onFocus={() => {
              if (draftLo === null) setDraftLo(String(lo));
            }}
            onChange={setDraftLo}
            onBlur={commitLo}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitLo();
              }
              if (e.key === "Escape") setDraftLo(null);
            }}
          />
          <SalaryBubble
            value={hi}
            draft={draftHi}
            pct={displayHiPct}
            caretOffsetPx={hiCaretOffsetPx}
            ariaLabel={t("common:salaryMax")}
            onFocus={() => {
              if (draftHi === null) setDraftHi(String(hi));
            }}
            onChange={setDraftHi}
            onBlur={commitHi}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitHi();
              }
              if (e.key === "Escape") setDraftHi(null);
            }}
          />
        </div>
        <div className="sm:mt-2">
          <RangeSlider
            min={SALARY_FORM_MIN}
            max={SALARY_FORM_MAX}
            step={SALARY_FORM_STEP}
            value={[lo, hi]}
            onChange={([newLo, newHi]) => onChange(newLo, newHi)}
            ariaLabelMin={t("common:salaryMin")}
            ariaLabelMax={t("common:salaryMax")}
            shouldShowLabels={false}
          />
        </div>
      </div>

      <div className="mt-0.5 flex justify-between text-[10px] text-white/20">
        <span>₪{SALARY_FORM_MIN.toLocaleString("he-IL")}</span>
        <span>₪{SALARY_FORM_MAX.toLocaleString("he-IL")}</span>
      </div>
      <p className="text-start text-[11px] text-white/30">
        {t("common:salaryPerMonth")}
      </p>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
