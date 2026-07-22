import { useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import SettingsCard from "@/components/ui/SettingsCard";
import { requestAccountDeletion } from "@/services/candidate";

export default function AccountDeletionSection() {
  const { t } = useTranslation("candidate");
  const [state, setState] = useState<"idle" | "sent" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleRequest() {
    setBusy(true);
    setError(null);
    setState("idle");
    try {
      await requestAccountDeletion();
      setState("sent");
    } catch (err) {
      setState("error");
      setError(
        axios.isAxiosError(err) && err.response?.status === 429
          ? t("candidate:profile.deletion.errors.tooMany")
          : t("candidate:profile.deletion.errors.generic"),
      );
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
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7h6m-7 0V5a2 2 0 012-2h2a2 2 0 012 2v2"
          />
        </svg>
      }
      title={t("candidate:profile.deletion.title")}
    >
      <div className="flex flex-1 flex-col gap-3">
        <p className="text-xs text-white/55">
          {t("candidate:profile.deletion.description")}
        </p>
        <div className="mt-auto flex items-center justify-between gap-3">
          <div className="text-[11px]" role="status" aria-live="polite">
            {state === "sent" && (
              <span className="text-copper">
                {t("candidate:profile.deletion.sentMessage")}
              </span>
            )}
            {state === "error" && error && (
              <span className="text-danger">{error}</span>
            )}
          </div>
          <Button
            variant="danger"
            size="sm"
            disabled={busy || state === "sent"}
            onClick={handleRequest}
          >
            {busy
              ? t("candidate:profile.deletion.requesting")
              : t("candidate:profile.deletion.request")}
          </Button>
        </div>
      </div>
    </SettingsCard>
  );
}
