import { useState, type ReactNode } from "react";

import { useTranslation } from "react-i18next";

/**
 * Mobile-only collapsible card for admin list pages. The card shows a title
 * and optional status badge by default; tapping the row expands the body
 * (which is rendered via `children`) with a smooth grid-rows transition.
 *
 * A separate `actions` slot is rendered absolutely at the inline-end corner
 * so a 3-dot menu can sit alongside without triggering the expansion.
 *
 * - Dedicated chevron in a copper-bordered circle at the inline-start of the
 *   row makes the affordance unmissable.
 * - The card border tints copper when open.
 * - A "סגור" close button anchors the bottom of the expanded content.
 */
export default function MobileEntityCard({
  title,
  badge,
  actions,
  children,
}: {
  title: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation(['common', 'http']);
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div
      className={`relative overflow-hidden rounded-xl border bg-card transition-colors duration-200 ${
        isOpen
          ? "border-copper/40 bg-card-raised"
          : "border-white/8 hover:border-white/15"
      }`}
    >
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        aria-expanded={isOpen}
        aria-label={isOpen ? t("common:collapse") : t("common:expand")}
        className="flex w-full cursor-pointer items-center gap-3 px-3 py-3 pe-12 text-start active:scale-[0.99]"
      >
        <span
          className={`inline-flex size-7 shrink-0 items-center justify-center rounded-full border transition-colors duration-200 ${
            isOpen
              ? "border-copper bg-copper/15 text-copper"
              : "border-white/15 text-white/45"
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className={`size-3.5 transition-transform duration-300 ease-out ${isOpen ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M4.22 5.72a.75.75 0 0 1 1.06 0L8 8.44l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 6.78a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </span>
        <div className="min-w-0 flex-1 truncate font-medium text-white/85">
          {title}
        </div>
        {badge && <div className="shrink-0">{badge}</div>}
      </button>
      {actions && <div className="absolute end-1 top-2">{actions}</div>}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`border-t border-white/8 px-4 py-4 transition-opacity duration-200 ${
              isOpen ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            {children}
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2 text-xs font-medium text-white/65 transition-colors hover:border-copper/50 hover:text-copper active:scale-[0.99]"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                className="size-3.5"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M11.78 10.28a.75.75 0 0 1-1.06 0L8 7.56l-2.72 2.72a.75.75 0 1 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06Z"
                  clipRule="evenodd"
                />
              </svg>
              {t("common:collapse")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
