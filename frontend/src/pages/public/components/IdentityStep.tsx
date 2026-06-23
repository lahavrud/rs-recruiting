import { type ChangeEvent, type FocusEvent } from "react";

import { useTranslation } from "react-i18next";

import Field from "@/components/ui/Field";
import { INPUT_CLS } from "@/styles/forms";
import type { CandidateApplicationForm } from "@/types/candidates";
export default function IdentityStep({
  form,
  fieldErrors,
  onChange,
  onBlur,
  isEmailReadOnly = false,
}: {
  form: Omit<CandidateApplicationForm, "job_id">;
  fieldErrors: Record<string, string>;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  isEmailReadOnly?: boolean;
}) {
  const { t } = useTranslation(["publicJobs", "sm"]);
  return (
    <div className="grid gap-4 sm:grid-cols-2 sm:gap-x-6 sm:gap-y-5">
      <Field
        label={t("publicJobs:application.fullName")}
        id="full_name"
        required
        error={fieldErrors.full_name}
      >
        <input
          id="full_name"
          name="full_name"
          type="text"
          required
          value={form.full_name}
          onChange={onChange}
          onBlur={onBlur}
          className={INPUT_CLS}
          placeholder={t("publicJobs:application.placeholders.fullName")}
          autoComplete="name"
          aria-invalid={!!fieldErrors.full_name}
        />
      </Field>

      <Field
        label={t("publicJobs:application.email")}
        id="email"
        required
        error={fieldErrors.email}
      >
        <input
          id="email"
          name="email"
          type="email"
          required
          value={form.email}
          onChange={onChange}
          onBlur={onBlur}
          className={INPUT_CLS}
          placeholder={t("publicJobs:application.placeholders.email")}
          autoComplete="email"
          aria-invalid={!!fieldErrors.email}
          readOnly={isEmailReadOnly}
          aria-readonly={isEmailReadOnly}
          title={
            isEmailReadOnly ? t("publicJobs:application.emailLockedHint") : undefined
          }
        />
      </Field>

      <Field
        label={t("publicJobs:application.phone")}
        id="phone"
        required
        error={fieldErrors.phone}
      >
        <input
          id="phone"
          name="phone"
          type="tel"
          value={form.phone}
          onChange={onChange}
          onBlur={onBlur}
          className={INPUT_CLS}
          placeholder={t("publicJobs:application.placeholders.phone")}
          autoComplete="tel"
          aria-invalid={!!fieldErrors.phone}
        />
      </Field>

      <Field
        label={t("publicJobs:application.linkedin")}
        id="linkedin_url"
        optional
        className="sm:col-span-2"
        error={fieldErrors.linkedin_url}
      >
        <input
          id="linkedin_url"
          name="linkedin_url"
          type="url"
          value={form.linkedin_url}
          onChange={onChange}
          onBlur={onBlur}
          className={INPUT_CLS}
          placeholder={t("publicJobs:application.placeholders.linkedin")}
          aria-invalid={!!fieldErrors.linkedin_url}
        />
      </Field>
    </div>
  );
}
