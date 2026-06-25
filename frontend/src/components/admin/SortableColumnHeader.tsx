import type { SortOrder } from "@/hooks/useColumnSort";

interface SortableColumnHeaderProps {
  label: string;
  active: boolean;
  order: SortOrder;
  onClick: () => void;
  /** Precedence badge for a multi-column cross-sort (1 = primary, 2 = secondary). */
  rank?: 1 | 2;
}

/**
 * Clickable `<th>` content for a sortable column — label + direction caret.
 * Caller still owns the `<th>` (padding/alignment classes); set
 * `aria-sort="ascending" | "descending"` on it when `active` for a11y.
 */
export default function SortableColumnHeader({
  label,
  active,
  order,
  onClick,
  rank,
}: SortableColumnHeaderProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 uppercase tracking-wide transition hover:text-white/70"
    >
      <span>{label}</span>
      {rank != null && (
        <sup className="text-[9px] font-semibold text-copper/70">{rank}</sup>
      )}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`h-2.5 w-2.5 shrink-0 self-center transition-all duration-200 ease-in-out ${
          active ? "text-copper" : "text-white/20"
        } ${order === "asc" ? "rotate-180" : ""}`}
        aria-hidden="true"
      >
        <path d="M4 6 L8 10 L12 6" />
      </svg>
    </button>
  );
}
