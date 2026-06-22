import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/ui/Logo";
import { inputCls } from "@/styles/forms";
import { registerCandidate } from "@/services/auth";
import { EMAIL_RE } from "@/utils/validators";
import Field from "@/components/ui/Field";
import Eyebrow from "@/components/ui/Eyebrow";
import Button from "@/components/ui/Button";

type FieldName =
  | "fullName"
  | "email"
  | "password"
  | "passwordConfirm"
  | "privacy"
  | "terms";

type FieldErrors = Partial<Record<FieldName, string>>;

const PASSWORD_RE = {
  upper: /[A-Z]/,
  lower: /[a-z]/,
  digit: /\d/,
  special: /[^A-Za-z0-9]/,
};
/**
 * Candidate self-registration form. Mirrors the company `RegisterPage`
 * shape: per-field inline errors validated on blur (cleared on next
 * keystroke), and TOS / privacy as modal-on-click summaries with a
 * checkbox to accept. The candidate flow is single-step (no signature,
 * no logo, no company details) so the layout stays tight.
 */
export default function RegisterCandidatePage() {
  const { t } = useTranslation(['auth', 'common', 'http', 'legal']);
  const { isAuthenticated } = useAuth();
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    password: "",
    passwordConfirm: "",
  });
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);

  // Lock background scroll while a policy modal is open — matches the
  // company register's behavior so the page doesn't twitch on close.
  useEffect(() => {
    if (termsOpen || privacyOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [termsOpen, privacyOpen]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  function validateField(name: FieldName, value: string): string {
    if (name === "fullName") {
      if (!value.trim())
        return t("auth:registerCandidate.validation.fullNameRequired");
      if (value.trim().length < 2)
        return t("auth:registerCandidate.validation.fullNameMin");
    }
    if (name === "email") {
      if (!value.trim())
        return t("auth:register.validation.emailRequired");
      if (!EMAIL_RE.test(value))
        return t("auth:register.validation.emailInvalid");
    }
    if (name === "password") {
      if (!value)
        return t("auth:register.validation.passwordRequired");
      if (value.length < 8)
        return t("auth:register.validation.passwordMin");
      if (
        !PASSWORD_RE.upper.test(value) ||
        !PASSWORD_RE.lower.test(value) ||
        !PASSWORD_RE.digit.test(value) ||
        !PASSWORD_RE.special.test(value)
      )
        return t("auth:registerCandidate.validation.passwordComplexity");
    }
    if (name === "passwordConfirm") {
      if (!value)
        return t("auth:register.validation.confirmRequired");
      if (value !== form.password)
        return t("auth:register.validation.confirmMismatch");
    }
    return "";
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name as FieldName]) {
      setFieldErrors((prev) => ({ ...prev, [name]: "" }));
    }
  }

  function handleBlur(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    const msg = validateField(name as FieldName, value);
    setFieldErrors((prev) => ({ ...prev, [name]: msg }));
  }

  function validateAll(): boolean {
    const errs: FieldErrors = {
      fullName: validateField("fullName", form.fullName),
      email: validateField("email", form.email),
      password: validateField("password", form.password),
      passwordConfirm: validateField("passwordConfirm", form.passwordConfirm),
      privacy: privacyAccepted
        ? ""
        : t("auth:register.validation.privacyRequired"),
      terms: termsAccepted
        ? ""
        : t("auth:register.validation.termsRequired"),
    };
    setFieldErrors(errs);
    return Object.values(errs).every((v) => !v);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!validateAll()) return;
    setSubmitting(true);
    try {
      await registerCandidate({
        email: form.email.trim().toLowerCase(),
        password: form.password,
        full_name: form.fullName.trim(),
        privacy_accepted: privacyAccepted,
        terms_accepted: termsAccepted,
      });
      setSubmitted(true);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 409)
          setFormError(t("auth:registerCandidate.errors.emailExists"));
        else if (status === 429)
          setFormError(t("auth:registerCandidate.errors.tooManyAttempts"));
        else if (status === 422)
          setFormError(t("auth:registerCandidate.errors.validation"));
        else setFormError(t("auth:registerCandidate.errors.generic"));
      } else {
        setFormError(t("auth:registerCandidate.errors.generic"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void px-4 py-8">
        <div className="w-full max-w-md space-y-6 rounded-xl border border-white/10 border-t-copper/50 bg-card p-8 text-center">
          <div className="flex justify-center">
            <Logo size={36} />
          </div>
          <h1 className="text-lg font-semibold text-white/85">
            {t("auth:registerCandidate.success.title")}
          </h1>
          <p className="text-sm text-white/60">
            {t("auth:registerCandidate.success.body")}
          </p>
          <Link
            to="/login"
            className="inline-block rounded-sm border border-white/20 px-4 py-2 text-sm text-white/70 transition hover:border-white/40 hover:text-white"
          >
            {t("auth:register.success.backToLogin")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-void px-4 py-8">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-white/10 border-t-copper/50 bg-card">
        <div className="px-6 pt-8 text-center sm:px-8">
          <div className="flex justify-center">
            <Logo size={36} />
          </div>
          <h1 className="mt-4 text-lg font-semibold text-white/85">
            {t("auth:registerCandidate.subtitle")}
          </h1>
          <p className="mt-1 text-xs text-white/40">
            {t("auth:registerCandidate.description")}
          </p>
        </div>

        <form
          className="space-y-5 px-6 sm:px-8"
          onSubmit={handleSubmit}
          noValidate
        >
          {formError && (
            <div className="rounded-lg border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
              {formError}
            </div>
          )}

          <Field
            label={t("auth:registerCandidate.fullNameLabel")}
            error={fieldErrors.fullName}
          >
            <input
              id="fullName"
              name="fullName"
              type="text"
              required
              autoComplete="name"
              value={form.fullName}
              onChange={handleChange}
              onBlur={handleBlur}
              className={inputCls}
              placeholder={t("auth:registerCandidate.fullNamePlaceholder")}
            />
          </Field>

          <Field
            label={t("auth:register.emailLabel")}
            error={fieldErrors.email}
          >
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={handleChange}
              onBlur={handleBlur}
              dir="ltr"
              className={inputCls}
              placeholder={t("auth:registerCandidate.emailPlaceholder")}
            />
          </Field>

          <Field
            label={t("auth:register.passwordLabel")}
            error={fieldErrors.password}
          >
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="new-password"
              value={form.password}
              onChange={handleChange}
              onBlur={handleBlur}
              className={inputCls}
              placeholder={t("auth:register.passwordPlaceholder")}
            />
          </Field>

          <Field
            label={t("auth:register.confirmLabel")}
            error={fieldErrors.passwordConfirm}
          >
            <input
              id="passwordConfirm"
              name="passwordConfirm"
              type="password"
              required
              autoComplete="new-password"
              value={form.passwordConfirm}
              onChange={handleChange}
              onBlur={handleBlur}
              className={inputCls}
              placeholder={t("auth:register.confirmPlaceholder")}
            />
          </Field>

          {/* ───────── Agreement section ───────── */}
          <div>
            <Eyebrow className="mb-2">
              {t("auth:register.agreementSection")}
            </Eyebrow>
            <AgreementCard
              title={t("auth:register.agreementSectionSiteTerms")}
              readFullLabel={t("auth:register.agreementReadFull")}
              onOpen={() => setTermsOpen(true)}
              checkboxLabel={t("auth:register.termsCheckboxLabel")}
              checked={termsAccepted}
              onChange={(v) => {
                setTermsAccepted(v);
                if (v) setFieldErrors((p) => ({ ...p, terms: "" }));
              }}
              error={fieldErrors.terms}
            />
            <div className="mt-2">
              <AgreementCard
                title={t("auth:register.agreementSectionPrivacy")}
                readFullLabel={t("auth:register.agreementReadFull")}
                onOpen={() => setPrivacyOpen(true)}
                checkboxLabel={t("auth:register.privacyCheckboxLabel")}
                checked={privacyAccepted}
                onChange={(v) => {
                  setPrivacyAccepted(v);
                  if (v) setFieldErrors((p) => ({ ...p, privacy: "" }));
                }}
                error={fieldErrors.privacy}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting
              ? t("auth:register.submittingText")
              : t("auth:register.submitText")}
          </button>
        </form>

        <p className="px-6 pb-8 text-center text-sm text-white/35 sm:px-8">
          <Link to="/login" className="text-copper transition hover:text-gold">
            {t("auth:registerCandidate.backToLoginLink")}
          </Link>
        </p>
      </div>

      {/* Policy modals — body text lives in the `legal` namespace, shared
          with the standalone policy pages, so it stays in one place. */}
      {termsOpen && (
        <PolicyModal
          title={t("auth:register.agreementSectionSiteTerms")}
          body={t("legal:terms.body")}
          acceptLabel={t("common:confirm")}
          closeLabel={t("common:close")}
          checked={termsAccepted}
          onAccept={() => {
            setTermsAccepted(true);
            setFieldErrors((p) => ({ ...p, terms: "" }));
            setTermsOpen(false);
          }}
          onClose={() => setTermsOpen(false)}
        />
      )}
      {privacyOpen && (
        <PolicyModal
          title={t("auth:register.agreementSectionPrivacy")}
          body={t("legal:privacy.body")}
          acceptLabel={t("common:confirm")}
          closeLabel={t("common:close")}
          checked={privacyAccepted}
          onAccept={() => {
            setPrivacyAccepted(true);
            setFieldErrors((p) => ({ ...p, privacy: "" }));
            setPrivacyOpen(false);
          }}
          onClose={() => setPrivacyOpen(false)}
        />
      )}
    </div>
  );
}

/** Agreement card with eyebrow title, "read full" link, and a checkbox. */
function AgreementCard({
  title,
  readFullLabel,
  onOpen,
  checkboxLabel,
  checked,
  onChange,
  error,
}: {
  title: string;
  readFullLabel: string;
  onOpen: () => void;
  checkboxLabel: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  error?: string;
}) {
  return (
    <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-white/65">{title}</p>
        <button
          type="button"
          onClick={onOpen}
          className="shrink-0 text-[11px] text-copper/75 transition hover:text-copper"
        >
          {readFullLabel}
        </button>
      </div>
      <label className="mt-3 flex cursor-pointer items-center gap-2.5 text-sm text-white/65">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="accent-copper"
        />
        <span>{checkboxLabel}</span>
      </label>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

/** Scrollable modal with the full policy text + accept/close buttons. */
function PolicyModal({
  title,
  body,
  acceptLabel,
  closeLabel,
  checked,
  onAccept,
  onClose,
}: {
  title: string;
  body: string;
  acceptLabel: string;
  closeLabel: string;
  checked: boolean;
  onAccept: () => void;
  onClose: () => void;
}) {
  const paragraphs = body.split("\n\n");
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-3">
          <h2 className="text-sm font-semibold text-white/85">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
            className="flex size-8 items-center justify-center text-white/50 transition hover:text-white"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="size-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18 18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4 text-sm leading-relaxed text-white/75">
          {paragraphs.map((p, i) => (
            <p key={i} className="whitespace-pre-line">
              {p}
            </p>
          ))}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-white/8 px-5 py-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
          >
            {closeLabel}
          </Button>
          <button
            type="button"
            onClick={onAccept}
            className="rounded-sm bg-copper px-4 py-1.5 text-sm font-medium text-white transition hover:bg-gold"
          >
            {checked ? closeLabel : acceptLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
