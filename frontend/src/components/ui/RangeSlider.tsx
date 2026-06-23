import { useCallback } from "react";

interface RangeSliderProps {
  min: number;
  max: number;
  step?: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  formatValue?: (n: number) => string;
  ariaLabelMin?: string;
  ariaLabelMax?: string;
  shouldShowLabels?: boolean;
  /** Enlarges thumbs from size-5 to size-7. */
  isLarge?: boolean;
}

// Two full static strings so Tailwind's scanner sees every class name.
const THUMB_BASE =
  "[&::-webkit-slider-thumb]:pointer-events-auto " +
  "[&::-webkit-slider-thumb]:relative [&::-webkit-slider-thumb]:z-20 " +
  "[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:appearance-none " +
  "[&::-webkit-slider-thumb]:bg-copper " +
  "[&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white/90 " +
  "[&::-webkit-slider-thumb]:shadow [&::-webkit-slider-thumb]:shadow-black/40 " +
  "[&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-colors " +
  "hover:[&::-webkit-slider-thumb]:bg-gold " +
  "[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:rounded-full " +
  "[&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white/90 " +
  "[&::-moz-range-thumb]:bg-copper [&::-moz-range-thumb]:cursor-pointer";

const THUMB_MD = `[&::-webkit-slider-thumb]:size-5 [&::-moz-range-thumb]:size-5 ${THUMB_BASE}`;
const THUMB_LG = `[&::-webkit-slider-thumb]:size-7 [&::-moz-range-thumb]:size-7 ${THUMB_BASE}`;

export default function RangeSlider({
  min,
  max,
  step = 1,
  value,
  onChange,
  formatValue = (n) => n.toString(),
  ariaLabelMin,
  ariaLabelMax,
  shouldShowLabels = true,
  isLarge = false,
}: RangeSliderProps) {
  const [valMin, valMax] = value;
  const thumbCls = isLarge ? THUMB_LG : THUMB_MD;

  const handleMinChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = Math.min(Number(e.target.value), valMax - step);
      onChange([Math.max(min, next), valMax]);
    },
    [valMax, onChange, step, min],
  );

  const handleMaxChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = Math.max(Number(e.target.value), valMin + step);
      onChange([valMin, Math.min(max, next)]);
    },
    [valMin, onChange, step, max],
  );

  const span = max - min || 1;
  const minPct = ((valMin - min) / span) * 100;
  const maxPct = ((valMax - min) / span) * 100;

  return (
    // Inherit page direction (RTL). The min thumb anchors to the start of
    // the inline axis (right in RTL, left in LTR) and labels follow suit.
    <div className="select-none">
      <div className={`relative ${isLarge ? "h-7" : "h-5"}`}>
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-white/8" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-copper/70"
          style={{
            insetInlineStart: `${minPct}%`,
            insetInlineEnd: `${100 - maxPct}%`,
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valMin}
          onChange={handleMinChange}
          aria-label={ariaLabelMin}
          className={`pointer-events-none absolute inset-x-0 top-0 w-full appearance-none bg-transparent ${isLarge ? "h-7" : "h-5"} ${thumbCls}`}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valMax}
          onChange={handleMaxChange}
          aria-label={ariaLabelMax}
          className={`pointer-events-none absolute inset-x-0 top-0 w-full appearance-none bg-transparent ${isLarge ? "h-7" : "h-5"} ${thumbCls}`}
        />
      </div>
      {shouldShowLabels && (
        <div className="mt-2 flex justify-between text-xs font-medium text-white/55">
          <span>{formatValue(valMin)}</span>
          <span>{formatValue(valMax)}</span>
        </div>
      )}
    </div>
  );
}
