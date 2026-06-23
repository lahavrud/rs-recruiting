import { useState } from "react";

import { useTranslation } from "react-i18next";

import PageHeader from "@/components/ui/PageHeader";
import { useFetch } from "@/hooks/useFetch";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import { getMe, type CandidateMeRead } from "@/services/candidate";
import { errorAlertClsLg } from "@/styles/forms";

import ApplyAutofillSection from "./components/ApplyAutofillSection";
import DataExportSection from "./components/DataExportSection";
import IdentitySection from "./components/IdentitySection";
import SecuritySection from "./components/SecuritySection";

/**
 * Candidate self-service profile (Sprint 11 / #608).
 *
 * Five sections, each owns its own submit-state so a failure on one
 * doesn't grey out the others:
 *  1. Identity         — name + email (email read-only). Only these two
 *                        are mandatory; everything below is optional
 *                        autofill metadata used by the apply form.
 *  2. Apply autofill   — phone + LinkedIn. Both nullable — clear to
 *                        remove. The apply form will prompt the
 *                        candidate inline if a live application is
 *                        missing phone.
 *  3. Resume           — current file + upload (replace) + remove
 *  4. Security         — change-password (current + new + confirm)
 *  5. Your data        — request GDPR export (emailed download link)
 */
export default function CandidateProfilePage() {
  const { t } = useTranslation('candidate');
  const [me, setMe] = useState<CandidateMeRead | null>(null);
  // Settings group is collapsed by default — it's account controls
  // (password, GDPR export), secondary to the profile content above.
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const { data: fetchedMe, loading, error: fetchError } = useFetch(getMe, []);
  useResetOnTrigger(fetchedMe, () => setMe(fetchedMe));
  const loadError = fetchError ? t("candidate:profile.errors.loadFailed") : null;

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <div className="text-white/40">{t("candidate:profile.loading")}</div>
      </div>
    );
  }
  if (loadError || !me) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className={errorAlertClsLg}>
          {loadError ?? t("candidate:profile.errors.loadFailed")}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow={t("candidate:profile.eyebrow")}
        subtitle={t("candidate:profile.subtitle")}
      />

      {/* ── Profile group ─────────────────────────────────────────────
          Identity sits on a slim, gradient-tinted strip. The
          autofill+resume card below is wider with an internal split
          (2-col on desktop) so phone/LinkedIn and the resume picker
          read as one cluster but visually distinct from identity. */}
      <div className="mt-6 space-y-4">
        <IdentitySection me={me} onChange={setMe} />
        <ApplyAutofillSection me={me} onChange={setMe} />
      </div>

      {/* ── Settings group ────────────────────────────────────────────
          Collapsible — these are account-level controls (password,
          GDPR export), secondary to the profile content above. Default
          collapsed; expanding uses the grid-template-rows 0fr↔1fr
          trick (same as the dashboard's profile-completion expand) so
          the height interpolates without measuring with JS. */}
      <div className="mt-10">
        <button
          type="button"
          onClick={() => setIsSettingsOpen((v) => !v)}
          aria-expanded={isSettingsOpen}
          aria-controls="candidate-settings-panel"
          className="group flex w-full items-center justify-between gap-2 border-b border-white/8 pb-2 transition-colors hover:border-white/15"
        >
          <span className="text-[10px] font-semibold uppercase tracking-widest text-white/40 transition-colors group-hover:text-white/60">
            {t("candidate:profile.settings.title")}
          </span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className={`size-4 text-white/40 transition-transform duration-200 ease-out ${
              isSettingsOpen ? "rotate-180" : ""
            }`}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m6 9 6 6 6-6"
            />
          </svg>
        </button>

        <div
          id="candidate-settings-panel"
          className="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
          style={{
            gridTemplateRows: isSettingsOpen ? "1fr" : "0fr",
            opacity: isSettingsOpen ? 1 : 0,
          }}
        >
          <div className="overflow-hidden">
            <div className="grid gap-3 pt-3 grid-cols-[minmax(0,1fr)] sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <SecuritySection />
              <DataExportSection />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
