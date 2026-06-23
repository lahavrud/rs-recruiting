import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import JobBoardFilterPanel from "./JobBoardFilterPanel";

import type { FilterPanelProps } from "./JobBoardFilterPanel";

interface MobileFilterDrawerProps extends FilterPanelProps {
  open: boolean;
  onClose: () => void;
  filteredCount: number;
}

export default function MobileFilterDrawer({
  open,
  onClose,
  filteredCount,
  ...filterPanelProps
}: MobileFilterDrawerProps) {
  const { t } = useTranslation(['common', 'http', 'ltr', 'publicJobs']);

  return createPortal(
    <div
      className={`fixed inset-0 z-[100] lg:hidden ${open ? "pointer-events-auto" : "pointer-events-none"}`}
      aria-hidden={!open}
    >
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-black/65 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0"}`}
      />
      <div
        className={`absolute inset-y-0 start-0 flex w-[88%] max-w-sm flex-col bg-card-raised shadow-2xl shadow-black/50 transition-transform duration-200 ease-out ${open ? "translate-x-0" : "ltr:-translate-x-full rtl:translate-x-full"}`}
        role="dialog"
        aria-modal="true"
        aria-label={t("publicJobs:board.filters")}
      >
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
          <p className="text-sm font-semibold text-white/90">
            {t("publicJobs:board.filters")}
          </p>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common:close")}
            className="rounded-sm p-1 text-white/55 transition hover:text-white"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              className="size-4"
              aria-hidden="true"
            >
              <path d="M3.28 2.22a.75.75 0 0 0-1.06 1.06L6.94 8l-4.72 4.72a.75.75 0 1 0 1.06 1.06L8 9.06l4.72 4.72a.75.75 0 1 0 1.06-1.06L9.06 8l4.72-4.72a.75.75 0 0 0-1.06-1.06L8 6.94 3.28 2.22Z" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">
          <JobBoardFilterPanel {...filterPanelProps} shouldShowSearch />
        </div>
        <div className="border-t border-white/8 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-sm bg-copper py-2.5 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("publicJobs:board.showResults", { count: filteredCount })}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
