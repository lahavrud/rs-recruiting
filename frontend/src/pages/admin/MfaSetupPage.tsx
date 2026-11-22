import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import QRCode from "qrcode";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Logo from "@/components/ui/Logo";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/hooks/useAuth";
import AuthShell from "@/pages/components/AuthShell";
import { MFA_SETUP_PATH } from "@/services/api";
import { confirmMfaEnrolment, startMfaEnrolment } from "@/services/auth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";
import type { MfaEnrolmentStart } from "@/types/auth";
import { apiErrorInfo, normalizeTotp, TOTP_LENGTH } from "@/utils/mfa";

import RecoveryCodesList from "./components/RecoveryCodesList";

const QR_SIZE_PX = 200;
// Base32 keys are typed by hand from this screen: groups of 4 read easier.
const KEY_GROUP_RE = /.{1,4}/g;
const COPIED_RESET_MS = 2000;

type SetupState =
  | { step: "loading" }
  | { step: "error" }
  | { step: "scan"; secret: string; qrDataUrl: string }
  | { step: "done"; recoveryCodes: string[] };

/**
 * Admin TOTP enrolment (#1177): scan, confirm with a code, save recovery
 * codes. An admin without MFA is routed here by the guards and the API.
 */
export default function MfaSetupPage() {
  const { t } = useTranslation(["admin", "ui"]);
  const { refreshUserFromToken, logout } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState<SetupState>({ step: "loading" });
  const [code, setCode] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAcknowledged, setIsAcknowledged] = useState(false);
  const [isKeyCopied, setIsKeyCopied] = useState(false);
  const [isLeaveBlocked, setIsLeaveBlocked] = useState(false);
  const doneHeadingRef = useRef<HTMLHeadingElement>(null);
  // One enrolment request per page, even when StrictMode runs the effect
  // twice: a second start would replace the secret behind the first QR.
  const startRef = useRef<Promise<MfaEnrolmentStart> | null>(null);

  /** Let the app see the stored token's new mfa claim; a bad one logs out. */
  const adoptStoredToken = useCallback(() => {
    try {
      refreshUserFromToken();
    } catch {
      navigate("/login", { replace: true });
    }
  }, [navigate, refreshUserFromToken]);

  // `navigate` changes identity on every navigation, re-running this effect;
  // only the first live run may act on the start result, or a later run
  // would put the page back on the scan step and hide the recovery codes.
  const isStartSettledRef = useRef(false);

  useEffect(() => {
    let isActive = true;
    startRef.current ??= startMfaEnrolment();
    startRef.current
      .then(async ({ secret, otpauth_uri }) => {
        const qrDataUrl = await QRCode.toDataURL(otpauth_uri, {
          margin: 1,
          width: QR_SIZE_PX,
        });
        if (!isActive || isStartSettledRef.current) return;
        isStartSettledRef.current = true;
        setState({ step: "scan", secret, qrDataUrl });
      })
      .catch((err) => {
        if (!isActive || isStartSettledRef.current) return;
        isStartSettledRef.current = true;
        // Already enrolled (stale token): nothing to set up here.
        if (apiErrorInfo(err).status === 409) {
          adoptStoredToken();
          navigate("/dashboard", { replace: true });
          return;
        }
        setState({ step: "error" });
      });
    return () => {
      isActive = false;
    };
  }, [navigate, adoptStoredToken]);

  // The codes are shown once: until they're saved, nothing may leave them.
  // The page has no app nav (bare shell); closing the tab gets the browser's
  // warning, and Back is held by an extra same-URL history entry that is
  // re-armed on every Back. (BrowserRouter has no useBlocker.)
  const isCodesUnsaved = state.step === "done" && !isAcknowledged;
  useEffect(() => {
    if (!isCodesUnsaved) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    const holdBack = () => {
      navigate(MFA_SETUP_PATH, { state: { holdsRecoveryCodes: true } });
      setIsLeaveBlocked(true);
    };
    navigate(MFA_SETUP_PATH, { state: { holdsRecoveryCodes: true } });
    window.addEventListener("beforeunload", warn);
    window.addEventListener("popstate", holdBack);
    return () => {
      window.removeEventListener("beforeunload", warn);
      window.removeEventListener("popstate", holdBack);
    };
  }, [isCodesUnsaved, navigate]);

  useEffect(() => {
    if (state.step === "done") doneHeadingRef.current?.focus();
  }, [state.step]);

  useEffect(() => {
    if (!isKeyCopied) return;
    const timer = setTimeout(() => setIsKeyCopied(false), COPIED_RESET_MS);
    return () => clearTimeout(timer);
  }, [isKeyCopied]);

  async function handleConfirm(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      const { recovery_codes } = await confirmMfaEnrolment(code);
      setState({ step: "done", recoveryCodes: recovery_codes });
      // MFA is on now: adopt the token at once, so leaving this page (any
      // nav link) can't bounce back here and lose the one-time codes.
      adoptStoredToken();
    } catch (err) {
      const { status, detail } = apiErrorInfo(err);
      if (status === 401 && detail === "invalid_mfa_code") {
        setFormError(t("admin:mfa.setup.invalidCode"));
      } else if (status === 429) {
        setFormError(t("admin:mfa.setup.tooManyAttempts"));
      } else {
        setFormError(t("admin:mfa.setup.confirmError"));
      }
      setCode("");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCopyKey(secret: string) {
    try {
      await navigator.clipboard.writeText(secret);
      setIsKeyCopied(true);
    } catch {
      // Clipboard blocked: the key is on screen to type.
    }
  }

  return (
    <AuthShell>
      <div className="w-full max-w-xl">
        <div className="mb-6 flex items-center justify-between">
          <Logo size={32} />
          {state.step !== "done" && (
            <Button type="button" variant="ghost" size="sm" onClick={logout}>
              {t("ui:header.logout")}
            </Button>
          )}
        </div>
        <PageHeader
          eyebrow={t("admin:mfa.setup.eyebrow")}
          subtitle={t("admin:mfa.setup.subtitle")}
        />

        {state.step === "loading" && <div className="h-64" aria-busy="true" />}

        {state.step === "error" && (
          <div role="alert" className={errorAlertCls}>
            {t("admin:mfa.setup.loadError")}
          </div>
        )}

        {state.step === "scan" && (
          <form
            className="space-y-6 rounded-xl border border-white/6 bg-card p-6"
            onSubmit={handleConfirm}
          >
            <div className="space-y-3">
              <p className="text-sm text-white/70">{t("admin:mfa.setup.step1")}</p>
              <img
                src={state.qrDataUrl}
                alt={t("admin:mfa.setup.qrAlt")}
                width={QR_SIZE_PX}
                height={QR_SIZE_PX}
                className="mx-auto rounded-md"
              />
              <p className="text-xs text-white/50">{t("admin:mfa.setup.manualKey")}</p>
              <div className="flex items-center gap-2">
                <code
                  dir="ltr"
                  className="block flex-1 rounded-md bg-well px-3 py-2 text-center font-mono text-sm tracking-wide text-white/85 [overflow-wrap:anywhere]"
                  data-testid="mfa-secret"
                >
                  {state.secret.match(KEY_GROUP_RE)?.join(" ")}
                </code>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => handleCopyKey(state.secret)}
                >
                  {isKeyCopied
                    ? t("admin:mfa.setup.done.copied")
                    : t("admin:mfa.setup.copyKey")}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-white/70">{t("admin:mfa.setup.step2")}</p>
              <label htmlFor="mfa-setup-code" className="block text-sm text-white/50">
                {t("admin:mfa.setup.codeLabel")}
              </label>
              <input
                id="mfa-setup-code"
                dir="ltr"
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                value={code}
                aria-invalid={formError ? true : undefined}
                onChange={(e) => setCode(normalizeTotp(e.target.value))}
                className={`text-center tracking-widest ${INPUT_CLS}`}
              />
              {formError && (
                <div role="alert" className={errorAlertCls}>
                  {formError}
                </div>
              )}
            </div>

            <Button
              type="submit"
              disabled={isSubmitting || code.length < TOTP_LENGTH}
              className="w-full"
            >
              {isSubmitting
                ? t("admin:mfa.setup.confirming")
                : t("admin:mfa.setup.confirm")}
            </Button>
          </form>
        )}

        {state.step === "done" && (
          <div className="space-y-5 rounded-xl border border-white/6 bg-card p-6">
            <p className="text-sm text-success">{t("admin:mfa.setup.done.enabled")}</p>
            <h2
              ref={doneHeadingRef}
              tabIndex={-1}
              className="text-base font-medium text-white/85 focus:outline-none"
            >
              {t("admin:mfa.setup.done.title")}
            </h2>
            <p className="text-sm text-white/60">{t("admin:mfa.setup.done.body")}</p>
            <RecoveryCodesList codes={state.recoveryCodes} />
            {isLeaveBlocked && isCodesUnsaved && (
              <div role="alert" className={errorAlertCls}>
                {t("admin:mfa.setup.done.saveFirst")}
              </div>
            )}
            <p className="text-xs text-white/45">
              {t("admin:mfa.setup.done.lostBoth")}
            </p>
            <label className="flex cursor-pointer items-center gap-2 py-2 text-sm text-white/60">
              <input
                type="checkbox"
                checked={isAcknowledged}
                onChange={(e) => setIsAcknowledged(e.target.checked)}
                className="h-4 w-4 cursor-pointer rounded border-white/20 bg-well accent-copper"
              />
              {t("admin:mfa.setup.done.ack")}
            </label>
            <Button
              type="button"
              disabled={!isAcknowledged}
              onClick={() => navigate("/dashboard", { replace: true })}
              className="w-full"
            >
              {t("admin:mfa.setup.done.continue")}
            </Button>
          </div>
        )}
      </div>
    </AuthShell>
  );
}
