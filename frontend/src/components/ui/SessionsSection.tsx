import { useState } from "react";

import { useTranslation } from "react-i18next";

import { useAuth } from "@/hooks/useAuth";
import { useFetch } from "@/hooks/useFetch";
import {
  listSessions,
  revokeAllSessions,
  revokeSession,
  type SessionRead,
} from "@/services/candidate";
import { apiErrorKey } from "@/utils/apiError";
import { formatTimeAgo } from "@/utils/formatDate";

import Button from "./Button";
import SettingsCard from "./SettingsCard";

function parseDevice(ua: string | null, fallback: string): string {
  if (!ua) return fallback;

  const os =
    /iPhone|iPad/.test(ua)
      ? "iOS"
      : /Android/.test(ua)
        ? "Android"
        : /Windows NT/.test(ua)
          ? "Windows"
          : /Macintosh/.test(ua)
            ? "macOS"
            : /Linux/.test(ua)
              ? "Linux"
              : null;

  const browser =
    /Edg\//.test(ua)
      ? "Edge"
      : /OPR\//.test(ua)
        ? "Opera"
        : /Chrome\//.test(ua)
          ? "Chrome"
          : /Firefox\//.test(ua)
            ? "Firefox"
            : /Safari\//.test(ua)
              ? "Safari"
              : null;

  if (browser && os) return `${browser} / ${os}`;
  if (browser) return browser;
  if (os) return os;
  return fallback;
}

export default function SessionsSection() {
  const { t } = useTranslation("ui");
  const { logout } = useAuth();
  const [refreshTick, setRefreshTick] = useState(0);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [revokingAll, setRevokingAll] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: sessions, loading } = useFetch(listSessions, [refreshTick]);

  async function handleRevoke(s: SessionRead) {
    setRevokingId(s.id);
    setActionError(null);
    try {
      await revokeSession(s.id);
      if (s.is_current) {
        logout();
      } else {
        setRefreshTick((n) => n + 1);
      }
    } catch (err) {
      setActionError(t(apiErrorKey(err, { 429: "ui:sessions.errors.tooMany" })));
      setRevokingId(null);
    }
  }

  async function handleRevokeAll() {
    setRevokingAll(true);
    setActionError(null);
    try {
      await revokeAllSessions();
      logout();
    } catch (err) {
      setActionError(t(apiErrorKey(err, { 429: "ui:sessions.errors.tooMany" })));
      setRevokingAll(false);
    }
  }

  const list: SessionRead[] = sessions ?? [];
  const unknownDevice = t("ui:sessions.unknownDevice");

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
      title={t("ui:sessions.title")}
    >
      <p className="mb-3 text-xs text-white/55">
        {t("ui:sessions.description")}
      </p>

      {loading && (
        <p className="text-xs text-white/30">{t("ui:sessions.loading")}</p>
      )}

      {!loading && list.length === 0 && (
        <p className="text-xs text-white/40">{t("ui:sessions.empty")}</p>
      )}

      {!loading && list.length > 0 && (
        <ul className="mb-3 divide-y divide-white/6">
          {list.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between gap-2 py-2"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="truncate text-xs font-medium text-white/70">
                    {parseDevice(s.user_agent, unknownDevice)}
                  </p>
                  {s.is_current && (
                    <span className="shrink-0 rounded-full bg-copper/15 px-1.5 py-px text-[10px] font-medium text-copper">
                      {t("ui:sessions.currentDevice")}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-[11px] text-white/35">
                  {formatTimeAgo(s.created_at)}
                </p>
              </div>
              <Button
                variant="ghost-danger"
                size="xs"
                className="shrink-0"
                disabled={revokingId === s.id || revokingAll}
                onClick={() => handleRevoke(s)}
              >
                {revokingId === s.id
                  ? t("ui:sessions.revoking")
                  : t("ui:sessions.revoke")}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex items-center justify-between gap-3">
        <div className="text-[11px]">
          {actionError && <span className="text-danger">{actionError}</span>}
        </div>
        {list.length > 0 && (
          <Button
            variant="ghost-danger"
            size="sm"
            disabled={revokingAll || revokingId !== null}
            onClick={handleRevokeAll}
          >
            {revokingAll
              ? t("ui:sessions.loggingOut")
              : t("ui:sessions.logoutAll")}
          </Button>
        )}
      </div>
    </SettingsCard>
  );
}
