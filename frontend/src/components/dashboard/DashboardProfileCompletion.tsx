import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import type { CandidateMeRead } from "@/services/candidate";

import { InlineEditor, type MissingKey } from "./DashboardInlineEditor";

// Matches the `duration-200` on the expand/collapse transition below.
// Centralised so the unmount delay stays in lockstep with the CSS timing.
const EXPAND_TRANSITION_MS = 200;

export function ProfileCompletion({
  me,
  onMeChange,
}: {
  me: CandidateMeRead | null;
  onMeChange: (next: CandidateMeRead) => void;
}) {
  const { t } = useTranslation('dashboard');
  const [expanded, setExpanded] = useState<MissingKey | null>(null);
  // Keeps the inline editor mounted during the close animation so the
  // collapse looks symmetric to the open. Set synchronously by ``open``
  // and cleared asynchronously by the close-side effect once the
  // transition has finished and the row has visibly closed.
  const [renderField, setRenderField] = useState<MissingKey | null>(null);

  function open(key: MissingKey) {
    setExpanded(key);
    setRenderField(key);
  }
  function close() {
    setExpanded(null);
  }
  function toggle(key: MissingKey) {
    if (expanded === key) close();
    else open(key);
  }

  useEffect(() => {
    if (expanded !== null) return;
    const timeout = setTimeout(() => setRenderField(null), EXPAND_TRANSITION_MS);
    return () => clearTimeout(timeout);
  }, [expanded]);

  // Loading: a minimal stripe placeholder. Once me is loaded and the
  // profile is fully filled, render nothing — the component is purely
  // a nudge for incomplete profiles.
  if (me === null) {
    return (
      <div className="relative overflow-hidden rounded-md border border-white/6 bg-card/40">
        <div className="absolute inset-y-0 start-0 w-0.5 bg-copper/60" />
        <div className="flex items-center gap-3 ps-4 pe-3 py-2.5">
          <div className="h-3 w-24 animate-pulse rounded bg-white/10" />
          <div className="h-6 w-20 animate-pulse rounded-sm bg-white/5" />
          <div className="h-6 w-24 animate-pulse rounded-sm bg-white/5" />
        </div>
      </div>
    );
  }

  const slots: { key: MissingKey; filled: boolean; label: string }[] = [
    {
      key: "phone",
      filled: !!me.phone,
      label: t("dashboard:candidate.profileCompletion.fields.phone"),
    },
    {
      key: "linkedin",
      filled: !!me.linkedin_url,
      label: t("dashboard:candidate.profileCompletion.fields.linkedin"),
    },
    {
      key: "resume",
      filled: !!me.resume_path,
      label: t("dashboard:candidate.profileCompletion.fields.resume"),
    },
  ];
  const missing = slots.filter((s) => !s.filled);

  // Profile is complete — render nothing. The nudge has served its
  // purpose and the dashboard reclaims the vertical space.
  if (missing.length === 0) return null;

  return (
    <div className="group/profile-completion relative overflow-hidden rounded-md border border-white/6 bg-card/40 transition-colors">
      {/* Asymmetric copper accent stripe — anchors the eye to the start
          of the row without painting the whole card copper. */}
      <div className="absolute inset-y-0 start-0 w-0.5 bg-copper/70" />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 ps-4 pe-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">
          {t("dashboard:candidate.profileCompletion.title")}{" "}
          <span className="text-white/55">
            {slots.length - missing.length}/{slots.length}
          </span>
        </p>

        <span className="text-xs text-white/35">·</span>

        <ul className="flex flex-wrap items-center gap-1.5">
          {missing.map((s) => (
            <li key={s.key}>
              <button
                type="button"
                onClick={() => toggle(s.key)}
                aria-expanded={expanded === s.key}
                className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-[11px] transition-all duration-150 ease-out ${
                  expanded === s.key
                    ? "bg-copper/15 text-copper"
                    : "text-white/55 hover:bg-copper/10 hover:text-copper/85"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`transition-transform duration-200 ease-out ${
                    expanded === s.key ? "rotate-45" : ""
                  }`}
                >
                  +
                </span>
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Animated reveal — the grid-template-rows 0fr↔1fr trick lets CSS
          interpolate the auto height without measuring with JS. Opacity
          adds a subtle fade so the editor doesn't pop in at full
          strength while the row is still collapsing/expanding. */}
      <div
        className="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
        style={{
          gridTemplateRows: expanded ? "1fr" : "0fr",
          opacity: expanded ? 1 : 0,
        }}
      >
        <div className="overflow-hidden">
          {renderField && (
            <div className="border-t border-white/6 bg-card-raised/40 ps-4 pe-3 py-3">
              <InlineEditor
                key={renderField}
                field={renderField}
                me={me}
                onSaved={(next) => {
                  onMeChange(next);
                  close();
                }}
                onCancel={close}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
