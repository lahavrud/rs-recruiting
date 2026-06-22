import { useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import { requestDataExport } from "@/services/candidate";

import SettingsCard from "./SettingsCard";

export default function DataExportSection() {
  const { t } = useTranslation('candidate');
  const [state, setState] = useState<"idle" | "queued" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleRequest() {
    setBusy(true);
    setError(null);
    setState("idle");
    try {
      await requestDataExport();
      setState("queued");
    } catch (err) {
      setState("error");
      setError(
        axios.isAxiosError(err) && err.response?.status === 429
          ? t("candidate:profile.export.errors.alreadyPending")
          : t("candidate:profile.export.errors.generic"),
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
            d="M12 3v12m0 0-4-4m4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
          />
        </svg>
      }
      title={t("candidate:profile.export.title")}
    >
      <div className="flex flex-1 flex-col gap-3">
        <p className="text-xs text-white/55">
          {t("candidate:profile.export.description")}
        </p>
        <div className="mt-auto flex items-center justify-between gap-3">
          <div className="text-[11px]">
            {state === "queued" && (
              <span className="text-copper">
                {t("candidate:profile.export.queuedMessage")}
              </span>
            )}
            {state === "error" && error && (
              <span className="text-danger">{error}</span>
            )}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={handleRequest}
            className="rounded-sm border border-white/20 px-3 py-1.5 text-xs text-white/80 transition hover:border-copper/50 hover:text-copper disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy
              ? t("candidate:profile.export.requesting")
              : t("candidate:profile.export.request")}
          </button>
        </div>
      </div>
    </SettingsCard>
  );
}
