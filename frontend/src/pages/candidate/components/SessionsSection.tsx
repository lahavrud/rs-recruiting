import { useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import { useFetch } from "@/hooks/useFetch";
import {
  listSessions,
  revokeAllSessions,
  revokeSession,
  type SessionRead,
} from "@/services/candidate";
import { formatDate } from "@/utils/formatDate";

import SettingsCard from "./SettingsCard";

export default function SessionsSection() {
  const { t } = useTranslation("candidate");
  const [refreshTick, setRefreshTick] = useState(0);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [revokingAll, setRevokingAll] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: sessions, loading } = useFetch(listSessions, [refreshTick]);

  async function handleRevoke(id: number) {
    setRevokingId(id);
    setActionError(null);
    try {
      await revokeSession(id);
      setRefreshTick((n) => n + 1);
    } catch {
      setActionError(t("candidate:profile.sessions.errors.revoke"));
    } finally {
      setRevokingId(null);
    }
  }

  async function handleRevokeAll() {
    setRevokingAll(true);
    setActionError(null);
    try {
      await revokeAllSessions();
      setRefreshTick((n) => n + 1);
    } catch (err) {
      setActionError(
        axios.isAxiosError(err) && err.response?.status === 429
          ? t("candidate:profile.sessions.errors.tooMany")
          : t("candidate:profile.sessions.errors.revokeAll"),
      );
    } finally {
      setRevokingAll(false);
    }
  }

  const list: SessionRead[] = sessions ?? [];

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
            d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"
          />
        </svg>
      }
      title={t("candidate:profile.sessions.title")}
    >
      <p className="mb-3 text-xs text-white/55">
        {t("candidate:profile.sessions.description")}
      </p>

      {loading && (
        <p className="text-xs text-white/30">{t("candidate:profile.loading")}</p>
      )}

      {!loading && list.length === 0 && (
        <p className="text-xs text-white/40">
          {t("candidate:profile.sessions.empty")}
        </p>
      )}

      {!loading && list.length > 0 && (
        <ul className="mb-3 divide-y divide-white/6">
          {list.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between gap-2 py-2"
            >
              <div className="text-xs text-white/60">
                <span>{formatDate(s.created_at)}</span>
                <span className="mx-1.5 text-white/25">→</span>
                <span className="text-white/40">{formatDate(s.expires_at)}</span>
              </div>
              <button
                type="button"
                disabled={revokingId === s.id || revokingAll}
                onClick={() => handleRevoke(s.id)}
                className="shrink-0 rounded-sm border border-white/10 px-2 py-1 text-[11px] text-white/50 transition hover:border-danger/50 hover:text-danger disabled:cursor-not-allowed disabled:opacity-40"
              >
                {revokingId === s.id
                  ? t("candidate:profile.sessions.revoking")
                  : t("candidate:profile.sessions.revoke")}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex items-center justify-between gap-3">
        <div className="text-[11px]">
          {actionError && <span className="text-danger">{actionError}</span>}
        </div>
        {list.length > 0 && (
          <button
            type="button"
            disabled={revokingAll || revokingId !== null}
            onClick={handleRevokeAll}
            className="rounded-sm border border-white/20 px-3 py-1.5 text-xs text-white/80 transition hover:border-danger/50 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
          >
            {revokingAll
              ? t("candidate:profile.sessions.loggingOut")
              : t("candidate:profile.sessions.logoutAll")}
          </button>
        )}
      </div>
    </SettingsCard>
  );
}
