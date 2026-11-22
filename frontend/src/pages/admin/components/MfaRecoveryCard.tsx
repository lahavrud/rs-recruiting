import { useEffect, useState, type FormEvent } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import SettingsCard from "@/components/ui/SettingsCard";
import { getMfaStatus, regenerateRecoveryCodes } from "@/services/auth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";
import {
  apiErrorInfo,
  normalizeTotp,
  retryAfterMinutes,
  TOTP_LENGTH,
} from "@/utils/mfa";

import RecoveryCodesList from "./RecoveryCodesList";

// At or below this many unused codes, nudge the admin to issue a new set.
const LOW_CODES = 3;

/** Replace the MFA recovery codes; needs a current authenticator code. */
export default function MfaRecoveryCard() {
  const { t } = useTranslation("admin");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    let isActive = true;
    getMfaStatus()
      .then((status) => {
        if (isActive) setRemaining(status.recovery_codes_remaining);
      })
      .catch(() => {
        // The count is a hint; the card works without it.
      });
    return () => {
      isActive = false;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { recovery_codes } = await regenerateRecoveryCodes(code);
      setCodes(recovery_codes);
      setRemaining(recovery_codes.length);
      setCode("");
    } catch (err) {
      const { status, detail } = apiErrorInfo(err);
      const minutes = retryAfterMinutes(err);
      if (status === 401 && detail === "invalid_mfa_code") {
        setError(t("admin:mfa.recovery.invalidCode"));
      } else if (status === 429 && detail === "mfa_locked" && minutes) {
        setError(t("admin:mfa.recovery.lockedFor", { count: minutes }));
      } else if (status === 429) {
        setError(t("admin:mfa.recovery.tooManyAttempts"));
      } else {
        setError(t("admin:mfa.recovery.error"));
      }
      setCode("");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SettingsCard
      icon={
        <svg
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
          stroke="currentColor"
          strokeWidth={1.8}
          className="size-4"
        >
          <circle cx="7.5" cy="15.5" r="4.5" />
          <path d="m10.7 12.3 9.8-9.8M17 6l3 3M14 9l2 2" />
        </svg>
      }
      title={t("admin:mfa.recovery.title")}
    >
      <p className="mb-3 text-sm text-white/55">{t("admin:mfa.recovery.body")}</p>
      {remaining !== null && !codes && (
        <p
          className={
            remaining <= LOW_CODES
              ? "mb-3 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"
              : "mb-3 text-sm text-white/55"
          }
          role={remaining <= LOW_CODES ? "status" : undefined}
          data-testid="recovery-remaining"
        >
          {remaining <= LOW_CODES && "⚠ "}
          {t("admin:mfa.recovery.remaining", { count: remaining })}
          {remaining <= LOW_CODES && ` ${t("admin:mfa.recovery.low")}`}
        </p>
      )}
      {codes ? (
        <div className="space-y-3">
          <p className="text-sm text-white/70">{t("admin:mfa.recovery.newCodes")}</p>
          <RecoveryCodesList codes={codes} />
          <Button type="button" size="sm" onClick={() => setCodes(null)}>
            {t("admin:mfa.recovery.saved")}
          </Button>
        </div>
      ) : (
        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={handleSubmit}
        >
          <div className="flex-1">
            <label htmlFor="mfa-recovery-code" className="block text-xs text-white/50">
              {t("admin:mfa.recovery.codeLabel")}
            </label>
            <input
              id="mfa-recovery-code"
              dir="ltr"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              value={code}
              aria-invalid={error ? true : undefined}
              onChange={(e) => setCode(normalizeTotp(e.target.value))}
              className={`mt-1 text-center tracking-widest ${INPUT_CLS}`}
            />
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={isSubmitting || code.length < TOTP_LENGTH}
          >
            {isSubmitting
              ? t("admin:mfa.recovery.generating")
              : t("admin:mfa.recovery.generate")}
          </Button>
        </form>
      )}
      {!codes && (
        <p className="mt-2 text-xs text-white/45">{t("admin:mfa.recovery.invalidatesOld")}</p>
      )}
      {error && (
        <div role="alert" className={`mt-2 ${errorAlertCls}`}>
          {error}
        </div>
      )}
    </SettingsCard>
  );
}
