import type { ReactNode } from "react";

/**
 * The animated open/close container every admin filter panel sits in.
 *
 * Animates `grid-template-rows` between `0fr` and `1fr` rather than a
 * `max-height` guess, so the panel expands to its true content height however
 * many filters a page puts inside it.
 */
export default function FilterPanelShell({
  isOpen,
  children,
}: {
  isOpen: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={`mb-4 grid transition-[grid-template-rows] duration-300 ease-out ${
        isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
      }`}
    >
      <div className="overflow-hidden">
        <div
          className={`space-y-4 rounded-md border border-white/8 bg-card/40 p-4 transition-opacity duration-200 ${
            isOpen ? "opacity-100 delay-100" : "opacity-0"
          }`}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
