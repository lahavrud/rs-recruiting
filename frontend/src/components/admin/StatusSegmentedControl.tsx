export interface StatusSegmentConfig {
  sliderCls: string;
  activeCls: string;
  dotCls: string;
}

interface StatusSegmentedControlProps<T extends string> {
  statuses: T[];
  value: T;
  onChange: (s: T) => void;
  config: Record<string, StatusSegmentConfig>;
  labelFor: (s: T) => string;
  ariaLabel: string;
}

/** Status as a segmented control — sliding highlight encodes selection independent of color. Shared by Jobs' `StatusPills` and the Applications record header. */
export default function StatusSegmentedControl<T extends string>({
  statuses,
  value,
  onChange,
  config,
  labelFor,
  ariaLabel,
}: StatusSegmentedControlProps<T>) {
  const activeIdx = statuses.indexOf(value);
  const cfg = config[value];

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="relative mt-1 flex overflow-hidden rounded-lg border border-white/10 bg-well"
    >
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-[3px] rounded-md border ${cfg.sliderCls}`}
        style={{
          width: `calc(100% / ${statuses.length})`,
          insetInlineStart: `calc(${activeIdx} * 100% / ${statuses.length})`,
          transition:
            "inset-inline-start 220ms cubic-bezier(0.4, 0, 0.2, 1), background-color 180ms ease, border-color 180ms ease",
        }}
      />

      {statuses.map((s) => {
        const isActive = value === s;
        const c = config[s];
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
            <span
              aria-hidden="true"
              className={`size-1.5 shrink-0 rounded-full transition-[opacity,transform] duration-200 ${c.dotCls} ${
                isActive ? "scale-100 opacity-100" : "scale-0 opacity-0"
              }`}
            />
            {labelFor(s)}
          </button>
        );
      })}
    </div>
  );
}
