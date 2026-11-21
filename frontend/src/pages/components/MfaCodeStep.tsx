import { useState, type FormEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/hooks/useAuth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";

const TOTP_LENGTH = 6;
const RECOVERY_CODE_MAX = 16;

interface MfaCodeStepProps {
  mfaToken: string;
  /** Logged in. */
  onDone: () => void;
  /** The challenge is dead (expired / too many tries): back to the password. */
  onRestart: (reason: "expired") => void;
}

/** Second step of an MFA login: an authenticator code or a recovery code. */
export default function MfaCodeStep({ mfaToken, onDone, onRestart }: MfaCodeStepProps) {
  const { t } = useTranslation("auth");
  const { completeMfaLogin } = useAuth();
  const [isRecovery, setIsRecovery] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const entered = value.trim();
    if (!entered) {
      setError(t("auth:login.mfa.errors.required"));
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await completeMfaLogin(
        mfaToken,
        isRecovery ? { recovery_code: entered } : { code: entered.replace(/\s/g, "") },
      );
      onDone();
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
      if (status === 401 && detail === "mfa_challenge_expired") {
        onRestart("expired");
      } else if (status === 401) {
        setError(t("auth:login.mfa.errors.invalidCode"));
        setValue("");
      } else if (status === 429) {
        setError(t("auth:login.errors.tooManyAttempts"));
      } else {
        setError(t("auth:login.errors.unexpectedError"));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function toggleMode() {
    setIsRecovery((prev) => !prev);
    setValue("");
    setError(null);
  }

  return (
    <form className="space-y-5 px-6 sm:px-8" onSubmit={handleSubmit}>
      <p className="text-sm text-white/60">
        {isRecovery ? t("auth:login.mfa.recoveryHint") : t("auth:login.mfa.codeHint")}
      </p>
      {error && <div className={errorAlertCls}>{error}</div>}
      <div>
        <label htmlFor="mfa-code" className="block text-sm text-white/50">
          {isRecovery
            ? t("auth:login.mfa.recoveryLabel")
            : t("auth:login.mfa.codeLabel")}
        </label>
        <input
          id="mfa-code"
          name="mfa-code"
          autoFocus
          dir="ltr"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className={`mt-1 text-center tracking-widest ${INPUT_CLS}`}
          {...(isRecovery
            ? {
                autoComplete: "off",
                maxLength: RECOVERY_CODE_MAX,
                placeholder: "xxxxx-xxxxx",
              }
            : {
                inputMode: "numeric" as const,
                autoComplete: "one-time-code",
                maxLength: TOTP_LENGTH,
                pattern: "[0-9]*",
                placeholder: "123456",
              })}
        />
      </div>
      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
      >
        {isSubmitting ? t("auth:login.submittingText") : t("auth:login.mfa.submit")}
      </button>
      <button
        type="button"
        onClick={toggleMode}
        className="w-full text-center text-sm text-copper transition hover:text-gold"
      >
        {isRecovery ? t("auth:login.mfa.useCode") : t("auth:login.mfa.useRecovery")}
      </button>
    </form>
  );
}
