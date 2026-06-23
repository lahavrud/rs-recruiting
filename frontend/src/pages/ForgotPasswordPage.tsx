import { type ChangeEvent, type FormEvent, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";

import Logo from "@/components/ui/Logo";
import { useAuth } from "@/hooks/useAuth";
import { requestPasswordReset } from "@/services/auth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";
import { apiErrorKey } from "@/utils/apiError";

import AuthShell from "./components/AuthShell";

export default function ForgotPasswordPage() {
  const { t } = useTranslation('auth');
  const { isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  function validate(value: string): string {
    if (!value.trim()) return t("auth:forgotPassword.validation.emailRequired");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
      return t("auth:forgotPassword.validation.emailInvalid");
    return "";
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    setEmail(e.target.value);
    if (emailError) setEmailError("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const err = validate(email);
    if (err) {
      setEmailError(err);
      return;
    }
    setSubmitting(true);
    try {
      await requestPasswordReset(email.trim());
      setSubmitted(true);
    } catch (err) {
      setError(t(apiErrorKey(err, { 429: "auth:forgotPassword.errors.tooManyAttempts" })));
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <AuthShell>
        <div className="w-full max-w-md rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="flex justify-center">
            <Logo size={32} />
          </div>
          <div className="mx-auto mt-6 flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth:forgotPassword.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth:forgotPassword.success.message")}
          </p>
          <Link
            to="/login"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("auth:forgotPassword.success.backToLogin")}
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div className="w-full max-w-sm space-y-8 rounded-xl border border-white/10 border-t-copper/50 bg-card sm:max-w-md">
        <div className="px-6 pt-8 text-center sm:px-8">
          <div className="flex justify-center">
            <Logo size={36} />
          </div>
          <h1 className="mt-4 text-lg font-semibold text-white/85">
            {t("auth:forgotPassword.title")}
          </h1>
          <p className="mt-2 text-sm text-white/45">
            {t("auth:forgotPassword.subtitle")}
          </p>
        </div>

        <form className="space-y-5 px-6 sm:px-8" onSubmit={handleSubmit} noValidate>
          {error && <div className={errorAlertCls}>{error}</div>}

          <div>
            <label htmlFor="email" className="block text-sm text-white/50">
              {t("auth:forgotPassword.emailLabel")}
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              value={email}
              onChange={handleChange}
              onBlur={(e) => setEmailError(validate(e.target.value))}
              className={`mt-1 ${INPUT_CLS}`}
              placeholder={t("auth:forgotPassword.emailPlaceholder")}
              autoComplete="email"
              dir="ltr"
            />
            {emailError && (
              <p className="mt-1 text-xs text-danger">{emailError}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting
              ? t("auth:forgotPassword.submittingText")
              : t("auth:forgotPassword.submitText")}
          </button>
        </form>

        <p className="px-6 pb-8 text-center text-sm text-white/35 sm:px-8">
          <Link to="/login" className="text-copper transition hover:text-gold">
            {t("auth:forgotPassword.backToLogin")}
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
