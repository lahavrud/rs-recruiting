import { useState, type ReactNode } from "react";

import RailToggleIcon from "@/components/admin/RailToggleIcon";

interface SplitPaneLayoutProps {
  rail: ReactNode;
  record: ReactNode;
  /** When this flips false→true the rail auto-collapses; true→false auto-expands. */
  recordPresent?: boolean;
  showListLabel: string;
  hideListLabel: string;
  /** Dialogs/overlays owned by the page, rendered after the layout. */
  children?: ReactNode;
}

/** Master–detail shell shared by every admin record workspace.
 *  The rail auto-collapses when a record is selected so the detail view
 *  gets full width, and reopens when the selection is cleared. The edge
 *  handle is always reachable to override this manually. */
export default function SplitPaneLayout({
  rail,
  record,
  recordPresent = false,
  showListLabel,
  hideListLabel,
  children,
}: SplitPaneLayoutProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [prevRecordPresent, setPrevRecordPresent] = useState(recordPresent);

  if (prevRecordPresent !== recordPresent) {
    setPrevRecordPresent(recordPresent);
    if (recordPresent) setCollapsed(true);
    else setCollapsed(false);
  }

  return (
    <div className="relative flex h-full min-h-0 flex-col md:flex-row">
      {/* Rail — transitions width; inner div keeps content at full width so
          items don't reflowing during the animation. */}
      <div
        className={`hidden min-h-0 flex-none overflow-hidden transition-[width] duration-300 ease-in-out md:block ${
          collapsed ? "w-0" : "w-72"
        }`}
      >
        <div className="h-full w-72 overflow-y-auto">{rail}</div>
      </div>

      {/* Edge toggle strip — always 16px wide, nearly invisible until hovered */}
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        aria-label={collapsed ? showListLabel : hideListLabel}
        title={collapsed ? showListLabel : hideListLabel}
        className="group/toggle relative hidden w-4 shrink-0 cursor-pointer items-stretch md:flex"
      >
        {/* Vertical separator line */}
        <div className="absolute inset-y-0 start-1/2 w-px -translate-x-1/2 bg-white/8 transition-colors duration-200 group-hover/toggle:bg-copper/40" />
        {/* Chevron pill — fades in on hover */}
        <div className="absolute top-1/2 start-1/2 flex size-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-transparent bg-transparent text-transparent transition-all duration-200 group-hover/toggle:border-white/12 group-hover/toggle:bg-card-raised group-hover/toggle:text-white/45">
          <RailToggleIcon className="size-3.5" flipped={collapsed} />
        </div>
      </button>

      {/* Record pane */}
      <div className="min-h-0 flex-1 overflow-y-auto md:min-w-0">{record}</div>

      {children}
    </div>
  );
}
