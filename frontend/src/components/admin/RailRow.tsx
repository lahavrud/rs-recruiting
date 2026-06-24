import type { ReactNode, Ref } from "react";

interface RailRowProps {
  selected?: boolean;
  onClick: () => void;
  actions?: ReactNode;
  rowRef?: Ref<HTMLDivElement>;
  children: ReactNode;
}

/** Selectable card row shared by every entity rail list (candidates, applications, …) at the 360px master list. */
export default function RailRow({ selected, onClick, actions, rowRef, children }: RailRowProps) {
  return (
    <div
      ref={rowRef}
      onClick={onClick}
      aria-selected={selected}
      className={`relative flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 pe-12 transition active:scale-[0.99] ${
        selected
          ? "border-copper/40 bg-card-raised"
          : "border-white/8 bg-card hover:border-white/15"
      }`}
    >
      {children}
      {actions && (
        <div className="absolute end-1 top-2" onClick={(e) => e.stopPropagation()}>
          {actions}
        </div>
      )}
    </div>
  );
}
