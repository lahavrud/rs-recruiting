import { useState } from "react";

import { useTranslation } from "react-i18next";

import { getConsent, saveConsent, applyGtmConsent } from "@/utils/consent";

export default function CookieConsent() {
  const { t } = useTranslation('cookies');
  const [isVisible, setIsVisible] = useState(() => getConsent() === null);
  const [isClosing, setIsClosing] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAnalyticsEnabled, setIsAnalyticsEnabled] = useState(true);

  if (!isVisible) return null;

  function dismiss(isAnalytics: boolean) {
    saveConsent({ analytics: isAnalytics });
    applyGtmConsent(isAnalytics);
    setIsClosing(true);
    setTimeout(() => setIsVisible(false), 260);
  }

  return (
    <div
      className={`fixed bottom-4 inset-x-4 sm:inset-x-auto sm:end-4 sm:w-80 z-50 ${
        isClosing ? "animate-cookie-down" : "animate-cookie-up"
      }`}
    >
      <div className="overflow-hidden rounded-xl border border-white/10 bg-void shadow-2xl ring-1 ring-white/5">
        {/* Settings panel — animated expand/collapse */}
        <div
          className={`overflow-hidden transition-[max-height,opacity] duration-300 ease-in-out ${
            isSettingsOpen ? "max-h-80 opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <div className="space-y-4 border-b border-white/8 px-4 pb-4 pt-4">
            {/* Necessary — always on */}
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white/90">
                  {t("cookies:necessary.title")}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-white/45">
                  {t("cookies:necessary.description")}
                </p>
              </div>
              <span className="mt-0.5 shrink-0 whitespace-nowrap rounded-full bg-copper/20 px-2 py-0.5 text-[10px] font-medium text-copper">
                {t("cookies:alwaysOn")}
              </span>
            </div>

            {/* Analytics — toggleable */}
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white/90">
                  {t("cookies:analytics.title")}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-white/45">
                  {t("cookies:analytics.description")}
                </p>
              </div>
              {/* dir="ltr" keeps thumb positioning physical so RTL layout doesn't offset it */}
              <button
                dir="ltr"
                type="button"
                role="switch"
                aria-checked={isAnalyticsEnabled}
                aria-label={t("cookies:analytics.title")}
                onClick={() => setIsAnalyticsEnabled((v) => !v)}
                className={`relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-copper/60 ${
                  isAnalyticsEnabled ? "bg-copper" : "bg-white/20"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform duration-200 ${
                    isAnalyticsEnabled ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <button
              type="button"
              onClick={() => dismiss(isAnalyticsEnabled)}
              className="w-full rounded-sm bg-copper/15 py-1.5 text-xs font-medium text-copper transition-colors hover:bg-copper/25"
            >
              {t("cookies:savePreferences")}
            </button>
          </div>
        </div>

        {/* Main card */}
        <div className="px-4 py-3.5">
          {/* Header */}
          <div className="mb-2.5 flex items-center gap-2">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="shrink-0 text-copper"
              aria-hidden
            >
              {/* Cookie body — slightly organic shape */}
              <path
                d="M12 2C15 1.5 19 3.5 20.5 7C22 10 21.5 14 19.5 17C17.5 20 14 22 11 21.5C8 21 5 18.5 3.5 15.5C2 12.5 2.5 8.5 4.5 6C6.5 3.5 9 2.5 12 2Z"
                opacity="0.2"
              />
              <path
                d="M12 2C15 1.5 19 3.5 20.5 7C22 10 21.5 14 19.5 17C17.5 20 14 22 11 21.5C8 21 5 18.5 3.5 15.5C2 12.5 2.5 8.5 4.5 6C6.5 3.5 9 2.5 12 2Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              {/* Chocolate chips — rotated ellipses for a natural look */}
              <ellipse cx="8.5" cy="8.5" rx="1.5" ry="1"   transform="rotate(-25 8.5 8.5)" />
              <ellipse cx="14"  cy="7.5" rx="1.3" ry="0.9" transform="rotate(20 14 7.5)"   />
              <ellipse cx="7"   cy="14"  rx="1.3" ry="0.9" transform="rotate(35 7 14)"     />
              <ellipse cx="14.5" cy="14" rx="1.5" ry="1"   transform="rotate(-15 14.5 14)" />
              <ellipse cx="11"  cy="17.5" rx="1.1" ry="0.8" transform="rotate(10 11 17.5)" />
              {/* Crumb dots */}
              <circle cx="11"  cy="11" r="0.5" />
              <circle cx="16.5" cy="11" r="0.4" />
            </svg>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-copper">
              {t("cookies:heading")}
            </span>
          </div>

          <p className="mb-3 text-[11px] leading-relaxed text-white/50">
            {t("cookies:banner")}
          </p>

          {/* Action row */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsSettingsOpen((v) => !v)}
              className="shrink-0 text-[11px] text-white/35 underline underline-offset-2 transition-colors hover:text-white/65"
            >
              {t("cookies:settings")}
            </button>
            <div className="flex flex-1 justify-end gap-2">
              <button
                type="button"
                onClick={() => dismiss(false)}
                className="rounded-sm border border-white/15 px-2.5 py-1.5 text-[11px] text-white/55 transition-colors hover:border-white/30 hover:text-white/80"
              >
                {t("cookies:essentialOnly")}
              </button>
              <button
                type="button"
                onClick={() => dismiss(true)}
                className="rounded-sm bg-copper px-2.5 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-gold"
              >
                {t("cookies:acceptAll")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
