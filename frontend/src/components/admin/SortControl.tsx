import DropdownMenu, { DropdownMenuItem } from "@/components/ui/DropdownMenu";
import type { SortOrder } from "@/hooks/useColumnSort";
import { SELECT_CLS } from "@/styles/forms";

import {
  findActiveOption,
  type ParsedSortKey,
  parseSortValue,
} from "./sortControlUtils";

interface SortControlProps {
  value: string;
  /**
   * `sort`/`order` are the option's primary key; `keys` is its full chain,
   * for options that also set a secondary sort (see `parseSortValue`).
   */
  onChange: (sort: string, order: SortOrder, keys: ParsedSortKey[]) => void;
  options: { value: string; label: string }[];
  ariaLabel: string;
}

/**
 * Compact mobile/rail equivalent of `SortableColumnHeader` — a themed
 * dropdown menu rather than a native `<select>`, whose OS-rendered picker
 * chrome breaks the dark UI on mobile. `value`/each option's `value` is the
 * combined `"<sort>:<order>"` key, or a comma-separated chain of them
 * (`"status:asc,created_at:desc"`) for an option with a secondary sort.
 */
export default function SortControl({
  value,
  onChange,
  options,
  ariaLabel,
}: SortControlProps) {
  const active = findActiveOption(options, value);

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
            const keys = parseSortValue(option.value);
            onChange(keys[0].column, keys[0].order, keys);
          }}
        >
          <span
            className={option === active ? "font-medium text-copper" : ""}
          >
            {option.label}
          </span>
        </DropdownMenuItem>
      ))}
    </DropdownMenu>
  );
}
