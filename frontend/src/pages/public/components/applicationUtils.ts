import axios from "axios";

import { checkPasswordComplexity } from "@/utils/passwordComplexity";
import { EMAIL_RE, MOBILE_RE } from "@/utils/validators";

import type { TFunction } from "i18next";

const TEXT_FIELD_MAX = 2000;

const STEP_3_FIELDS = [
  "service_concept",
  "salary_expectations",
  "strength",
  "growth_area",
] as const;

/**
 * Per-field validation rules for the application wizard.
 * Returns a translated error string, or null when the value is valid.
 */
export function validateField(
  t: TFunction,
  name: string,
  value: string,
): string | null {
  if (name === "full_name") {
    if (!value.trim())
      return t("publicJobs:application.validation.fullNameRequired");
    if (value.trim().length < 2)
      return t("publicJobs:application.validation.fullNameMin");
    if (value.length > 100)
      return t("publicJobs:application.validation.fullNameMax");
  }
  if (name === "email") {
    if (!value.trim())
      return t("publicJobs:application.validation.emailRequired");
    if (value.length > 255)
      return t("publicJobs:application.validation.emailMax");
    if (!EMAIL_RE.test(value))
      return t("publicJobs:application.validation.emailInvalid");
  }
  if (name === "phone") {
    if (!value.trim())
      return t("publicJobs:application.validation.phoneRequired");
    if (!MOBILE_RE.test(value.replace(/\D/g, "")))
      return t("publicJobs:application.validation.phoneFormat");
  }
  if (name === "linkedin_url" && value.trim()) {
    let parsed: URL;
    try {
      parsed = new URL(value);
    } catch {
      return t("publicJobs:application.validation.urlInvalid");
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return t("publicJobs:application.validation.urlProtocol");
    }
    if (!parsed.hostname.endsWith("linkedin.com")) {
      return t("publicJobs:application.validation.urlLinkedin");
    }
  }
  if (
    (STEP_3_FIELDS as readonly string[]).includes(name) &&
    value.length > TEXT_FIELD_MAX
  ) {
    return t("publicJobs:application.validation.textMax");
  }
  return null;
}

/**
 * Validates the claim-account password against the shared complexity rules.
 * Returns a translated error string, or null when the password is valid.
 */
export function validateClaimPassword(t: TFunction, val: string): string | null {
  const key = checkPasswordComplexity(val);
  return key ? t(key) : null;
}

/**
 * Maps a FastAPI error response to a translated Hebrew message.
 * Inspects the `detail` payload for application-specific error codes so
 * candidates see a meaningful message rather than a generic fallback.
 */
export function describeServerError(t: TFunction, err: unknown): string {
  if (!axios.isAxiosError(err)) {
    return t("publicJobs:application.errors.generic");
  }
  const httpStatus = err.response?.status;
  const detail = err.response?.data?.detail;
  if (httpStatus === 409) {
    const code = typeof detail === "object" ? detail?.error_code : null;
    // already_applied_editable is handled by the caller (redirect to edit
    // page); only the locked + email-collision cases need a string here.
    if (code === "already_applied_locked") {
      return t("publicJobs:application.errors.alreadyApplied");
    }
    if (code === "email_already_registered") {
      return t("publicJobs:application.errors.emailAlreadyRegistered");
    }
    return t("publicJobs:application.errors.alreadyApplied");
  }
  if (httpStatus === 404) {
    return t("publicJobs:application.errors.jobUnavailable");
  }
  if (httpStatus === 400) {
    if (detail === "privacy_consent_required") {
      return t("publicJobs:application.validation.privacyRequired");
    }
    if (detail === "terms_consent_required") {
      return t("publicJobs:application.validation.termsRequired");
    }
    if (detail === "passwords_do_not_match") {
      return t("publicJobs:application.validation.passwordMismatch");
    }
    return t("publicJobs:application.errors.generic");
  }
  return t("publicJobs:application.errors.generic");
}
