import { useEffect, useRef, useState, type FormEvent } from "react";

import axios from "axios";
import QRCode from "qrcode";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/hooks/useAuth";
import { confirmMfaEnrolment, startMfaEnrolment } from "@/services/auth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";
import type { MfaEnrolmentStart } from "@/types/auth";

import RecoveryCodesList from "./components/RecoveryCodesList";

const TOTP_LENGTH = 6;
const QR_SIZE_PX = 200;

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
  const { t } = useTranslation("admin");
  const { refreshUserFromToken } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState<SetupState>({ step: "loading" });
  const [code, setCode] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAcknowledged, setIsAcknowledged] = useState(false);
  // One enrolment request per page, even when StrictMode runs the effect
  // twice: a second start would replace the secret behind the first QR.
  const startRef = useRef<Promise<MfaEnrolmentStart> | null>(null);

  useEffect(() => {
    let isActive = true;
    startRef.current ??= startMfaEnrolment();
    startRef.current
      .then(async ({ secret, otpauth_uri }) => {
        const qrDataUrl = await QRCode.toDataURL(otpauth_uri, {
          margin: 1,
          width: QR_SIZE_PX,
        });
        if (isActive) setState({ step: "scan", secret, qrDataUrl });
      })
      .catch((err) => {
        if (!isActive) return;
        // Already enrolled (stale token): nothing to set up here.
        if (axios.isAxiosError(err) && err.response?.status === 409) {
          refreshUserFromToken();
          navigate("/dashboard", { replace: true });
          return;
        }
        setState({ step: "error" });
      });
    return () => {
      isActive = false;
    };
  }, [navigate, refreshUserFromToken]);

  async function handleConfirm(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      const { recovery_codes } = await confirmMfaEnrolment(code.replace(/\s/g, ""));
      setState({ step: "done", recoveryCodes: recovery_codes });
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      setFormError(
        status === 429
          ? t("admin:mfa.setup.tooManyAttempts")
          : t("admin:mfa.setup.invalidCode"),
      );
      setCode("");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleContinue() {
    // The stored token now carries mfa=true; let the guards see it.
    refreshUserFromToken();
    navigate("/dashboard", { replace: true });
  }

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader
        eyebrow={t("admin:mfa.setup.eyebrow")}
        subtitle={t("admin:mfa.setup.subtitle")}
      />

      {state.step === "loading" && <div className="h-64" aria-busy="true" />}

      {state.step === "error" && (
        <div className={errorAlertCls}>{t("admin:mfa.setup.loadError")}</div>
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
            <code
              dir="ltr"
              className="block break-all rounded-md bg-well px-3 py-2 text-center font-mono text-sm text-white/85"
              data-testid="mfa-secret"
            >
              {state.secret}
            </code>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-white/70">{t("admin:mfa.setup.step2")}</p>
            <label htmlFor="mfa-setup-code" className="block text-sm text-white/50">
              {t("admin:mfa.setup.codeLabel")}
            </label>
            <input
              id="mfa-setup-code"
              dir="ltr"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]*"
              maxLength={TOTP_LENGTH}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className={`text-center tracking-widest ${INPUT_CLS}`}
            />
            {formError && <div className={errorAlertCls}>{formError}</div>}
          </div>

          <Button
            type="submit"
            disabled={isSubmitting || code.trim().length < TOTP_LENGTH}
            className="w-full"
          >
            {isSubmitting ? t("admin:mfa.setup.confirming") : t("admin:mfa.setup.confirm")}
          </Button>
        </form>
      )}

      {state.step === "done" && (
        <div className="space-y-5 rounded-xl border border-white/6 bg-card p-6">
          <h2 className="text-base font-medium text-white/85">
            {t("admin:mfa.setup.done.title")}
          </h2>
          <p className="text-sm text-white/60">{t("admin:mfa.setup.done.body")}</p>
          <RecoveryCodesList codes={state.recoveryCodes} />
          <label className="flex cursor-pointer items-center gap-2 text-sm text-white/60">
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
            onClick={handleContinue}
            className="w-full"
          >
            {t("admin:mfa.setup.done.continue")}
          </Button>
        </div>
      )}
    </div>
  );
}
