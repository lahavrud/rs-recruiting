import { useState, type ChangeEvent, type FormEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Field from "@/components/ui/Field";
import { changePassword } from "@/services/candidate";
import { INPUT_CLS } from "@/styles/forms";

import SettingsCard from "./SettingsCard";

export default function SecuritySection() {
  const { t } = useTranslation('candidate');
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmNext, setConfirmNext] = useState("");
  const [state, setState] = useState<"idle" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (next !== confirmNext) {
      setState("error");
      setError(t("candidate:profile.security.errors.mismatch"));
      return;
    }
    setBusy(true);
    setError(null);
    setState("idle");
    try {
      await changePassword(current, next);
      setState("saved");
      setCurrent("");
      setNext("");
      setConfirmNext("");
    } catch (err) {
      setState("error");
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError(t("candidate:profile.security.errors.wrongCurrent"));
      } else if (axios.isAxiosError(err) && err.response?.status === 422) {
        setError(t("candidate:profile.security.errors.weakNew"));
      } else if (axios.isAxiosError(err) && err.response?.status === 429) {
        setError(t("candidate:profile.security.errors.tooMany"));
      } else {
        setError(t("candidate:profile.security.errors.generic"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <SettingsCard
      icon={
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          className="size-4"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 11c1.1 0 2-.9 2-2V7a2 2 0 0 0-4 0v2c0 1.1.9 2 2 2Zm-6 2v6a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2Z"
          />
        </svg>
      }
      title={t("candidate:profile.security.title")}
    >
      <form className="space-y-3" onSubmit={handleSubmit}>
        <Field label={t("candidate:profile.security.current")}>
          <input
            type="password"
            value={current}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setCurrent(e.target.value)
            }
            className={INPUT_CLS}
            autoComplete="current-password"
            required
          />
        </Field>
        <Field label={t("candidate:profile.security.new")}>
          <input
            type="password"
            value={next}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setNext(e.target.value)
            }
            className={INPUT_CLS}
            autoComplete="new-password"
            required
          />
        </Field>
        <Field label={t("candidate:profile.security.confirm")}>
          <input
            type="password"
            value={confirmNext}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setConfirmNext(e.target.value)
            }
            className={INPUT_CLS}
            autoComplete="new-password"
            required
          />
        </Field>
        <div className="flex items-center justify-between gap-3 pt-1">
          <div className="text-[11px]">
            {state === "saved" && (
              <span className="text-copper">
                {t("candidate:profile.security.saved")}
              </span>
            )}
            {state === "error" && error && (
              <span className="text-danger">{error}</span>
            )}
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-sm border border-white/20 px-3 py-1.5 text-xs text-white/80 transition hover:border-copper/50 hover:text-copper disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy
              ? t("candidate:profile.security.changing")
              : t("candidate:profile.security.change")}
          </button>
        </div>
      </form>
    </SettingsCard>
  );
}
