import type { ReactNode } from "react";

import * as RadixDropdown from "@radix-ui/react-dropdown-menu";

interface DropdownMenuProps {
  trigger: ReactNode;
  children: ReactNode;
  ariaLabel?: string;
  align?: "start" | "center" | "end";
}

/**
 * Standardized kebab/dropdown menu wrapper around Radix DropdownMenu with
 * the dark/luxury surface. Compose by rendering `<DropdownMenuItem>`
 * elements as children.
 */
export default function DropdownMenu({
  trigger,
  children,
  ariaLabel,
  align = "end",
}: DropdownMenuProps) {
  return (
    <RadixDropdown.Root>
      <RadixDropdown.Trigger asChild aria-label={ariaLabel}>
        {trigger}
      </RadixDropdown.Trigger>
      <RadixDropdown.Portal>
        <RadixDropdown.Content
          align={align}
          sideOffset={6}
          className="z-50 min-w-[12rem] rounded-md border border-white/10 bg-card-raised p-1 text-sm text-white/85 shadow-xl shadow-black/50"
        >
          {children}
        </RadixDropdown.Content>
      </RadixDropdown.Portal>
    </RadixDropdown.Root>
  );
}

interface ItemProps {
  children: ReactNode;
  onSelect: () => void;
  variant?: "default" | "danger";
  disabled?: boolean;
}

export function DropdownMenuItem({
  children,
  onSelect,
  variant = "default",
  disabled,
}: ItemProps) {
  const cls =
    variant === "danger"
      ? "text-danger hover:bg-danger/10"
      : "text-white/85 hover:bg-white/8";
  return (
    <RadixDropdown.Item
      disabled={disabled}
      onSelect={onSelect}
      className={[
        "flex cursor-pointer select-none items-center rounded-sm px-3 py-2 outline-none",
        "data-[highlighted]:bg-white/8 data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed",
        cls,
      ].join(" ")}
    >
      {children}
    </RadixDropdown.Item>
  );
}

export function DropdownMenuSeparator() {
  return <RadixDropdown.Separator className="my-1 h-px bg-white/10" />;
}
