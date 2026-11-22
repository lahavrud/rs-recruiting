import { useRef, useState, type FormEvent } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";
import {
  apiErrorInfo,
  normalizeTotp,
  retryAfterMinutes,
  TOTP_LENGTH,
} from "@/utils/mfa";

const RECOVERY_CODE_MAX = 16;

/** Why the user is sent back to the password step. */
export type MfaRestartReason = "expired" | "locked" | "cancel";

interface MfaCodeStepProps {
  mfaToken: string;
  /** The account being signed in to, shown so the user knows where they are. */
  email: string;
  /** Logged in. */
  onDone: () => void;
  /**
   * Back to the password: the challenge died, the account's code step is
   * locked (``minutes`` left, when the server said), or the user went back.
   */
  onRestart: (reason: MfaRestartReason, minutes?: number | null) => void;
}

/** Second step of an MFA login: an authenticator code or a recovery code. */
export default function MfaCodeStep({
  mfaToken,
  email,
  onDone,
  onRestart,
}: MfaCodeStepProps) {
  const { t } = useTranslation("auth");
  const { completeMfaLogin } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isRecovery, setIsRecovery] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const entered = value.trim();
  const isComplete = isRecovery ? entered.length > 0 : entered.length === TOTP_LENGTH;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isSubmitting) return; // Enter still submits while the button is disabled
    if (!isComplete) {
      setError(t("auth:login.mfa.errors.required"));
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await completeMfaLogin(
        mfaToken,
        isRecovery ? { recovery_code: entered } : { code: entered },
      );
      onDone();
    } catch (err) {
      const { status, detail } = apiErrorInfo(err);
      if (status === 401 && detail === "mfa_challenge_expired") {
        onRestart("expired");
      } else if (status === 429 && detail === "mfa_locked") {
        // No code is accepted until the lock ends, which outlives the
        // challenge: start over from the password, with the time left.
        onRestart("locked", retryAfterMinutes(err));
      } else if (status === 401 || status === 422) {
        setError(t("auth:login.mfa.errors.invalidCode"));
        setValue("");
        inputRef.current?.focus();
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
    // The same input is reused, so autoFocus won't fire again.
    inputRef.current?.focus();
  }

  return (
    <form className="space-y-5 px-6 pb-8 sm:px-8" onSubmit={handleSubmit} noValidate>
      <p className="text-sm text-white/60">
        {t("auth:login.mfa.signingInAs")}{" "}
        <bdi dir="ltr" className="text-white/85">
          {email}
        </bdi>
      </p>
      <p className="text-sm text-white/60">
        {isRecovery ? t("auth:login.mfa.recoveryHint") : t("auth:login.mfa.codeHint")}
      </p>
      {error && (
        <div role="alert" className={errorAlertCls}>
          {error}
        </div>
      )}
      <div>
        <label htmlFor="mfa-code" className="block text-sm text-white/50">
          {isRecovery
            ? t("auth:login.mfa.recoveryLabel")
            : t("auth:login.mfa.codeLabel")}
        </label>
        <input
          ref={inputRef}
          id="mfa-code"
          name="mfa-code"
          autoFocus
          dir="ltr"
          value={value}
          aria-invalid={error ? true : undefined}
          onChange={(e) =>
            setValue(isRecovery ? e.target.value : normalizeTotp(e.target.value))
          }
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
                placeholder: "123456",
              })}
        />
      </div>
      <Button
        type="submit"
        size="lg"
        disabled={isSubmitting || !isComplete}
        className="w-full"
      >
        {isSubmitting ? t("auth:login.mfa.verifying") : t("auth:login.mfa.submit")}
      </Button>
      <div className="flex flex-col items-center gap-3 text-sm">
        <button
          type="button"
          onClick={toggleMode}
          className="text-copper transition hover:text-gold"
        >
          {isRecovery ? t("auth:login.mfa.useCode") : t("auth:login.mfa.useRecovery")}
        </button>
        <button
          type="button"
          onClick={() => onRestart("cancel")}
          className="text-white/60 underline decoration-white/25 underline-offset-4 transition hover:text-white/85"
        >
          {t("auth:login.mfa.back")}
        </button>
      </div>
    </form>
  );
}
