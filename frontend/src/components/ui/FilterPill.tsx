import type { ButtonHTMLAttributes, ReactNode } from "react";

interface FilterPillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  isActive: boolean;
  /** Use px-2.5 instead of px-3 — for dense tag rows (e.g. locations). */
  compact?: boolean;
  children: ReactNode;
}

/**
 * Rounded-full toggle pill used by admin filter panels and `StatusPills`.
 * Active = copper fill; inactive = white/15 border that brightens on hover.
 */
export default function FilterPill({
  isActive,
  compact = false,
  className = "",
  children,
  ...props
}: FilterPillProps) {
  const padX = compact ? "px-2.5" : "px-3";
  return (
    <button
      type="button"
      {...props}
      className={`rounded-full ${padX} py-1 text-xs font-medium transition ${
        isActive
          ? "bg-copper text-white"
          : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85"
      } ${className}`}
    >
      {children}
    </button>
  );
}
