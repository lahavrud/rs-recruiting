import { useState, type ChangeEvent, type FocusEvent, type FormEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import Logo from "@/components/ui/Logo";
import { useAuth } from "@/hooks/useAuth";
import { resendCandidateActivation } from "@/services/auth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";
import { apiErrorKey } from "@/utils/apiError";
import { EMAIL_RE } from "@/utils/validators";

import AuthShell from "./components/AuthShell";

export default function LoginPage() {
  const { t } = useTranslation('auth');
  const { login, isAuthenticated, isInitializing } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const queryRedirect = searchParams.get("redirect");
  const stateFrom = (location.state as { from?: string } | null)?.from;
  // Query param wins (email links); only allow relative paths to prevent open redirect.
  const from = (queryRedirect?.startsWith("/") ? queryRedirect : null) ?? stateFrom ?? "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRememberMeChecked, setIsRememberMeChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({ email: "", password: "" });
  // When login fails with `account_pending_activation`, expose a resend link
  // tied to the email the user just entered. Cleared on next attempt.
  const [pendingActivationEmail, setPendingActivationEmail] = useState<string | null>(null);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );

  async function handleResendActivation() {
    if (!pendingActivationEmail || resendState === "sending") return;
    setResendState("sending");
    try {
      await resendCandidateActivation(pendingActivationEmail);
      setResendState("sent");
    } catch {
      setResendState("error");
    }
  }

  function validateField(name: string, value: string): string {
    if (name === "email") {
      if (!value.trim()) return t("auth:login.validation.emailRequired");
      if (!EMAIL_RE.test(value)) return t("auth:login.validation.emailInvalid");
    }
    if (name === "password") {
      if (!value.trim()) return t("auth:login.validation.passwordRequired");
      if (value.length < 8) return t("auth:login.validation.passwordMin");
    }
    return "";
  }

  function validateForm(): boolean {
    const errors = {
      email: validateField("email", email),
      password: validateField("password", password),
    };
    setFieldErrors(errors);
    return !errors.email && !errors.password;
  }

  function handleBlur(e: FocusEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    setFieldErrors((prev) => ({ ...prev, [name]: validateField(name, value) }));
  }

  function handleEmailChange(e: ChangeEvent<HTMLInputElement>) {
    setEmail(e.target.value);
    if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: "" }));
  }

  function handlePasswordChange(e: ChangeEvent<HTMLInputElement>) {
    setPassword(e.target.value);
    if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: "" }));
  }

  if (isInitializing) return null;
  if (isAuthenticated) return <Navigate to={from} replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPendingActivationEmail(null);
    setResendState("idle");
    if (!validateForm()) return;
    setIsSubmitting(true);
    try {
      await login({ email, password, remember_me: isRememberMeChecked });
      navigate(from, { replace: true });
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (status === 401) {
        const detail = (axios.isAxiosError(err) ? err.response?.data?.detail : "") as string;
        if (detail === "account_pending_activation") {
          setError(t("auth:login.errors.pendingActivation"));
          setPendingActivationEmail(email);
        } else if (detail === "account_pending_approval") {
          setError(t("auth:login.errors.pendingApproval"));
        } else if (detail === "account_inactive") {
          setError(t("auth:login.errors.accountInactive"));
        } else {
          setError(t("auth:login.errors.loginFailed"));
        }
      } else if (status === 429) {
        setError(t(apiErrorKey(err, { 429: "auth:login.errors.tooManyAttempts" })));
      } else if (status !== undefined) {
        setError(t("auth:login.errors.loginFailed"));
      } else {
        setError(t("auth:login.errors.unexpectedError"));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <div className="w-full max-w-sm space-y-8 rounded-xl border border-white/10 border-t-copper/50 bg-card sm:max-w-md">
        <div className="px-6 pt-8 text-center sm:px-8">
          <div className="flex justify-center">
            <Logo size={36} />
          </div>
          <h1 className="mt-4 text-lg font-semibold text-white/85">
            {t("auth:login.subtitle")}
          </h1>
        </div>

        <form className="space-y-5 px-6 sm:px-8" onSubmit={handleSubmit}>
          {error && (
            <div className={errorAlertCls}>
              {error}
              {pendingActivationEmail && (
                <div className="mt-2 text-xs text-white/60">
                  {resendState === "sent" ? (
                    <span>{t("auth:login.resendActivation.sent")}</span>
                  ) : resendState === "error" ? (
                    <span>{t("auth:login.resendActivation.error")}</span>
                  ) : (
                    <button
                      type="button"
                      onClick={handleResendActivation}
                      disabled={resendState === "sending"}
                      className="text-copper underline transition hover:text-gold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {resendState === "sending"
                        ? t("auth:login.resendActivation.sending")
                        : t("auth:login.resendActivation.cta")}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm text-white/50">
                {t("auth:login.emailLabel")}
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={email}
                onChange={handleEmailChange}
                onBlur={handleBlur}
                className={`mt-1 ${INPUT_CLS}`}
                placeholder={t("auth:login.emailPlaceholder")}
                autoComplete="email"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.email}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm text-white/50">
                {t("auth:login.passwordLabel")}
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={password}
                onChange={handlePasswordChange}
                onBlur={handleBlur}
                className={`mt-1 ${INPUT_CLS}`}
                placeholder={t("auth:login.passwordPlaceholder")}
                autoComplete="current-password"
              />
              {fieldErrors.password && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.password}</p>
              )}
            </div>
          </div>

          <label className="flex cursor-pointer items-center gap-2 text-sm text-white/50">
            <input
              type="checkbox"
              checked={isRememberMeChecked}
              onChange={(e) => setIsRememberMeChecked(e.target.checked)}
              className="h-4 w-4 cursor-pointer rounded border-white/20 bg-well accent-copper"
            />
            {t("auth:login.rememberMe")}
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isSubmitting ? t("auth:login.submittingText") : t("auth:login.submitText")}
          </button>
        </form>

        <div className="space-y-2 px-6 pb-8 text-center text-sm text-white/35 sm:px-8">
          <p>
            <Link
              to="/forgot-password"
              className="text-copper transition hover:text-gold"
            >
              {t("auth:login.forgotPasswordLink")}
            </Link>
          </p>
          <p>
            {t("auth:login.candidateSignupPrompt")}{" "}
            <Link
              to="/register-candidate"
              className="text-copper transition hover:text-gold"
            >
              {t("auth:login.candidateSignupLink")}
            </Link>
          </p>
        </div>
      </div>
    </AuthShell>
  );
}
