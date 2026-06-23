import { useState } from "react";

import { useTranslation } from "react-i18next";

import { INPUT_CLS } from "@/styles/forms";
import { checkPasswordComplexity } from "@/utils/passwordComplexity";

export default function ClaimAccountSection({
  isEnabled,
  onToggle,
  password,
  onPasswordChange,
  passwordConfirm,
  onPasswordConfirmChange,
  error,
}: {
  isEnabled: boolean;
  onToggle: (v: boolean) => void;
  password: string;
  onPasswordChange: (v: string) => void;
  passwordConfirm: string;
  onPasswordConfirmChange: (v: string) => void;
  error: string | null;
}) {
  const { t } = useTranslation(['publicJobs', 'sm']);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isPasswordTouched, setIsPasswordTouched] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  function validatePassword(val: string): string | null {
    if (!val) return null;
    const key = checkPasswordComplexity(val);
    return key ? t(key) : null;
  }

  function validateConfirm(val: string, pw: string): string | null {
    if (val && val !== pw) return t("publicJobs:application.validation.passwordMismatch");
    return null;
  }

  return (
    <div className="sm:col-span-2 mt-3 rounded-xl border border-white/10 bg-card p-4">
      <label className="flex cursor-pointer items-start gap-2.5">
        <input
          type="checkbox"
          checked={isEnabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 cursor-pointer accent-copper"
        />
        <span className="text-sm text-white/80">
          {t("publicJobs:application.claim.toggle")}
        </span>
      </label>
      <p className="mt-1 ms-7 text-xs text-white/50">
        {t("publicJobs:application.claim.description")}
      </p>

      {isEnabled && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label
              htmlFor="claim_password"
              className="block text-xs text-white/55"
            >
              {t("publicJobs:application.claim.passwordLabel")}
            </label>
            <input
              id="claim_password"
              name="claim_password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                onPasswordChange(e.target.value);
                if (isPasswordTouched) setPasswordError(validatePassword(e.target.value));
                if (confirmError && passwordConfirm) setConfirmError(validateConfirm(passwordConfirm, e.target.value));
              }}
              onBlur={(e) => {
                setIsPasswordTouched(true);
                setPasswordError(validatePassword(e.target.value));
              }}
              aria-invalid={!!passwordError}
              className={`mt-1 ${INPUT_CLS}`}
            />
            {passwordError ? (
              <p className="mt-1 text-xs text-danger">{passwordError}</p>
            ) : (
              <p className="mt-1 text-xs text-white/35">
                {t("publicJobs:application.claim.passwordHint")}
              </p>
            )}
          </div>
          <div>
            <label
              htmlFor="claim_password_confirm"
              className="block text-xs text-white/55"
            >
              {t("publicJobs:application.claim.passwordConfirmLabel")}
            </label>
            <input
              id="claim_password_confirm"
              name="claim_password_confirm"
              type="password"
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(e) => {
                onPasswordConfirmChange(e.target.value);
                if (confirmError) setConfirmError(null);
              }}
              onBlur={(e) => setConfirmError(validateConfirm(e.target.value, password))}
              aria-invalid={!!confirmError}
              className={`mt-1 ${INPUT_CLS}`}
            />
            {confirmError && (
              <p className="mt-1 text-xs text-danger">{confirmError}</p>
            )}
          </div>
          {error && (
            <p className="text-xs text-danger sm:col-span-2">{error}</p>
          )}
        </div>
      )}
    </div>
  );
}
