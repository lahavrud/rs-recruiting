import DropdownMenu, { DropdownMenuItem } from "@/components/ui/DropdownMenu";
import type { SortOrder } from "@/hooks/useColumnSort";
import { SELECT_CLS } from "@/styles/forms";

interface SortControlProps {
  value: string;
  onChange: (sort: string, order: SortOrder) => void;
  options: { value: string; label: string }[];
  ariaLabel: string;
}

/**
 * Compact mobile/rail equivalent of `SortableColumnHeader` — a themed
 * dropdown menu rather than a native `<select>`, whose OS-rendered picker
 * chrome breaks the dark UI on mobile. `value`/each option's `value` is the
 * combined `"<sort>:<order>"` key.
 */
export default function SortControl({
  value,
  onChange,
  options,
  ariaLabel,
}: SortControlProps) {
  const active = options.find((option) => option.value === value);

  return (
    <DropdownMenu
      align="start"
      ariaLabel={ariaLabel}
      contentClassName="w-[var(--radix-dropdown-menu-trigger-width)]"
      trigger={
        <button
          type="button"
          aria-label={ariaLabel}
          className={`${SELECT_CLS} flex w-full items-center justify-between gap-2 text-start transition-colors duration-200 active:scale-[0.99]`}
        >
          <span className="truncate">{active?.label ?? ariaLabel}</span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className="size-3.5 shrink-0 text-white/40"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M4.22 5.72a.75.75 0 0 1 1.06 0L8 8.44l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 6.78a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      }
    >
      {options.map((option) => (
        <DropdownMenuItem
          key={option.value}
          onSelect={() => {
            const [sort, order] = option.value.split(":");
            onChange(sort, order as SortOrder);
          }}
        >
          <span
            className={option.value === value ? "font-medium text-copper" : ""}
          >
            {option.label}
          </span>
        </DropdownMenuItem>
      ))}
    </DropdownMenu>
  );
}
