import { useState, type FormEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import SettingsCard from "@/components/ui/SettingsCard";
import { regenerateRecoveryCodes } from "@/services/auth";
import { errorAlertCls, INPUT_CLS } from "@/styles/forms";

import RecoveryCodesList from "./RecoveryCodesList";

const TOTP_LENGTH = 6;

/** Replace the MFA recovery codes; needs a current authenticator code. */
export default function MfaRecoveryCard() {
  const { t } = useTranslation("admin");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { recovery_codes } = await regenerateRecoveryCodes(code.replace(/\s/g, ""));
      setCodes(recovery_codes);
      setCode("");
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      setError(
        status === 401 ? t("admin:mfa.recovery.invalidCode") : t("admin:mfa.recovery.error"),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SettingsCard
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="size-4">
          <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      }
      title={t("admin:mfa.recovery.title")}
    >
      <p className="mb-3 text-sm text-white/55">{t("admin:mfa.recovery.body")}</p>
      {codes ? (
        <div className="space-y-2">
          <p className="text-sm text-white/70">{t("admin:mfa.recovery.newCodes")}</p>
          <RecoveryCodesList codes={codes} />
        </div>
      ) : (
        <form className="flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={handleSubmit}>
          <div className="flex-1">
            <label htmlFor="mfa-recovery-code" className="block text-xs text-white/50">
              {t("admin:mfa.recovery.codeLabel")}
            </label>
            <input
              id="mfa-recovery-code"
              dir="ltr"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={TOTP_LENGTH}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className={`mt-1 text-center tracking-widest ${INPUT_CLS}`}
            />
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={isSubmitting || code.trim().length < TOTP_LENGTH}
          >
            {isSubmitting ? t("admin:mfa.recovery.generating") : t("admin:mfa.recovery.generate")}
          </Button>
        </form>
      )}
      {error && <div className={`mt-2 ${errorAlertCls}`}>{error}</div>}
    </SettingsCard>
  );
}
