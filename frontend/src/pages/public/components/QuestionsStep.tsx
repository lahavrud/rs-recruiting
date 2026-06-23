import { type ChangeEvent, type FocusEvent } from "react";

import { useTranslation } from "react-i18next";

import Eyebrow from "@/components/ui/Eyebrow";
import Field from "@/components/ui/Field";
import { TEXTAREA_CLS as textareaBase } from "@/styles/forms";
import type { CandidateApplicationForm } from "@/types/candidates";
const TEXT_FIELD_MAX = 2000;
const TEXTAREA_CLS = textareaBase + " min-h-[96px]";

export default function QuestionsStep({
  form,
  fieldErrors,
  onChange,
  onBlur,
  isPrivacyAccepted,
  onPrivacyChange,
  onPrivacyOpen,
  isTermsAccepted,
  onTermsChange,
  onTermsOpen,
  isConsentHidden = false,
}: {
  form: Omit<CandidateApplicationForm, "job_id">;
  fieldErrors: Record<string, string>;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  isPrivacyAccepted: boolean;
  onPrivacyChange: (v: boolean) => void;
  onPrivacyOpen: () => void;
  isTermsAccepted: boolean;
  onTermsChange: (v: boolean) => void;
  onTermsOpen: () => void;
  isConsentHidden?: boolean;
}) {
  const { t } = useTranslation(["publicJobs", "sm"]);
  const fields: Array<{ name: keyof typeof form; label: string; ph: string }> = [
    {
      name: "service_concept",
      label: t("publicJobs:application.serviceConcept"),
      ph: t("publicJobs:application.placeholders.serviceConcept"),
    },
    {
      name: "salary_expectations",
      label: t("publicJobs:application.salaryExpectations"),
      ph: t("publicJobs:application.placeholders.salaryExpectations"),
    },
    {
      name: "strength",
      label: t("publicJobs:application.strength"),
      ph: t("publicJobs:application.placeholders.strength"),
    },
    {
      name: "growth_area",
      label: t("publicJobs:application.growthArea"),
      ph: t("publicJobs:application.placeholders.growthArea"),
    },
  ];
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="rounded-lg border border-copper/20 bg-copper/5 p-4 sm:col-span-2">
        <p className="text-xs leading-relaxed text-white/65">
          {t("publicJobs:application.questionsStepBanner")}
        </p>
      </div>

      {fields.map(({ name, label, ph }) => {
        const value = form[name] ?? "";
        const count = value.length;
        const isOverLimit = count > TEXT_FIELD_MAX;
        const isHalf = name === "strength" || name === "growth_area";
        return (
          <Field
            key={name}
            label={label}
            id={name}
            optional
            className={isHalf ? "sm:col-span-1" : "sm:col-span-2"}
          >
            <textarea
              id={name}
              name={name}
              value={value}
              onChange={onChange}
              onBlur={onBlur}
              className={TEXTAREA_CLS}
              placeholder={ph}
              maxLength={TEXT_FIELD_MAX}
              aria-invalid={!!fieldErrors[name]}
            />
            <div className="mt-1 flex items-start justify-between gap-2">
              <span className="text-xs text-danger">{fieldErrors[name] ?? ""}</span>
              <span
                className={`shrink-0 text-[11px] tabular-nums ${
                  isOverLimit ? "text-danger" : "text-white/30"
                }`}
              >
                {t("publicJobs:application.charCount", {
                  count,
                  max: TEXT_FIELD_MAX,
                })}
              </span>
            </div>
          </Field>
        );
      })}

      {/* Consent blocks are hidden for logged-in candidates — consent was
          captured at activation time (Sprint 11 / #605). */}
      {!isConsentHidden && (
        <>
          {/* Site Terms of Service consent — spans full width of the 2-col grid */}
          <div
            className={`sm:col-span-2 rounded-xl border p-4 transition-colors ${
              fieldErrors.terms
                ? "border-danger/40 bg-danger/5"
                : "border-white/10 bg-card"
            }`}
          >
            <Eyebrow>{t("publicJobs:application.termsConsentTitle")}</Eyebrow>
            <p className="mt-2 text-xs leading-relaxed text-white/55">
              {t("publicJobs:application.termsConsentPreview")}
            </p>
            <button
              type="button"
              onClick={onTermsOpen}
              className="mt-1 text-xs text-copper/80 underline-offset-2 hover:text-copper hover:underline"
            >
              {t("publicJobs:application.termsConsentReadFull")}
            </button>
            <label className="mt-3 flex cursor-pointer items-start gap-2.5">
              <input
                type="checkbox"
                checked={isTermsAccepted}
                onChange={(e) => onTermsChange(e.target.checked)}
                className="mt-0.5 size-4 shrink-0 cursor-pointer accent-copper"
                aria-describedby={fieldErrors.terms ? "terms-error" : undefined}
              />
              <span className="text-sm text-white/80">
                {t("publicJobs:application.termsConsentCheckbox")}
              </span>
            </label>
            {fieldErrors.terms && (
              <p id="terms-error" className="mt-2 text-xs text-danger">
                {fieldErrors.terms}
              </p>
            )}
          </div>

          {/* Privacy consent — spans full width of the 2-col grid */}
          <div
            className={`sm:col-span-2 rounded-xl border p-4 transition-colors ${
              fieldErrors.privacy
                ? "border-danger/40 bg-danger/5"
                : "border-white/10 bg-card"
            }`}
          >
            <Eyebrow>{t("publicJobs:application.privacyConsentTitle")}</Eyebrow>
            <p className="mt-2 text-xs leading-relaxed text-white/55">
              {t("publicJobs:application.privacyConsentPreview")}
            </p>
            <button
              type="button"
              onClick={onPrivacyOpen}
              className="mt-1 text-xs text-copper/80 underline-offset-2 hover:text-copper hover:underline"
            >
              {t("publicJobs:application.privacyConsentReadFull")}
            </button>
            <label className="mt-3 flex cursor-pointer items-start gap-2.5">
              <input
                type="checkbox"
                checked={isPrivacyAccepted}
                onChange={(e) => onPrivacyChange(e.target.checked)}
                className="mt-0.5 size-4 shrink-0 cursor-pointer accent-copper"
                aria-describedby={fieldErrors.privacy ? "privacy-error" : undefined}
              />
              <span className="text-sm text-white/80">
                {t("publicJobs:application.privacyConsentCheckbox")}
              </span>
            </label>
            {fieldErrors.privacy && (
              <p id="privacy-error" className="mt-2 text-xs text-danger">
                {fieldErrors.privacy}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
