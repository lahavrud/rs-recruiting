import type { ReactNode } from "react";

import RailToggleIcon from "./RailToggleIcon";

interface SplitPaneLayoutProps {
  rail: ReactNode;
  record: ReactNode;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  showListLabel: string;
  hideListLabel: string;
  /** Dialogs/overlays owned by the page, rendered after the layout. */
  children?: ReactNode;
}

/** Master–detail shell shared by every admin record-as-page workspace: a collapsible 360px rail, the record pane, and the floating toggle between them. */
export default function SplitPaneLayout({
  rail,
  record,
  collapsed,
  onToggleCollapsed,
  showListLabel,
  hideListLabel,
  children,
}: SplitPaneLayoutProps) {
  return (
    <div className="relative flex h-full min-h-0 flex-col md:flex-row">
      <div
        className={`hidden min-h-0 flex-col overflow-hidden transition-[width,opacity,margin] duration-300 ease-in-out md:flex md:flex-none ${
          collapsed ? "md:me-0 md:w-0 md:opacity-0" : "md:me-6 md:w-[360px] md:opacity-100"
        }`}
      >
        {rail}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto md:min-w-0">{record}</div>

      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? showListLabel : hideListLabel}
        title={collapsed ? showListLabel : hideListLabel}
        className={`absolute top-1/2 z-20 hidden size-9 -translate-y-1/2 translate-x-1/2 items-center justify-center rounded-full border border-white/10 bg-card-raised text-white/40 transition-all duration-300 ease-in-out hover:border-copper/30 hover:text-copper md:flex ${
          collapsed ? "start-0" : "start-[384px]"
        }`}
      >
        <RailToggleIcon className="size-4" flipped={collapsed} />
      </button>

      {children}
    </div>
  );
}
