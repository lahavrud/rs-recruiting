import { useTranslation } from "react-i18next";

import Eyebrow from "@/components/ui/Eyebrow";
import type {
  CandidateApplicationsPage,
  CandidateMeRead,
} from "@/services/candidate";
import { formatTodayHebrew } from "@/utils/formatDate";

import { profileCompletionPercent } from "./dashboardUtils";

// ─── Hero ─────────────────────────────────────────────────────────────────

export function Hero({
  me,
  appsPage,
}: {
  me: CandidateMeRead | null;
  appsPage: CandidateApplicationsPage | null;
}) {
  const { t } = useTranslation('dashboard');
  const today = formatTodayHebrew();
  const hour = new Date().getHours();
  const greetingKey =
    hour < 12
      ? "dashboard:greeting.morning"
      : hour < 17
        ? "dashboard:greeting.afternoon"
        : hour < 22
          ? "dashboard:greeting.evening"
          : "dashboard:greeting.night";

  // Prefer the candidate's actual first name from the profile; only
  // fall back to the email local-part while the fetch is in flight or
  // failed.
  const fullName = me?.full_name?.trim();
  const firstName = fullName ? fullName.split(/\s+/)[0] : undefined;

  const appsCount = appsPage?.items?.length ?? null;
  const completion = profileCompletionPercent(me);

  return (
    <header className="overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-br from-card-raised via-card to-card p-6 sm:p-8">
      <Eyebrow>{today}</Eyebrow>
      <h1 className="mt-3 text-2xl font-semibold text-white/90 sm:text-3xl">
        {t(greetingKey)}
        {firstName && <span className="text-copper/85">{`, ${firstName}`}</span>}
      </h1>
      <p className="mt-2 max-w-prose text-sm text-white/55">
        {t("dashboard:heroSubtitle.candidate")}
      </p>

      <dl className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-white/8 sm:grid-cols-2">
        <Stat
          label={t("dashboard:candidate.stats.applicationsSubmitted")}
          value={appsCount === null ? "—" : appsCount.toString()}
          hint={
            appsCount === 0
              ? t("dashboard:candidate.stats.applicationsHintEmpty")
              : appsCount === null
                ? ""
                : t("dashboard:candidate.stats.applicationsHint")
          }
        />
        <Stat
          label={t("dashboard:candidate.stats.profileCompletion")}
          value={completion === null ? "—" : `${completion}%`}
          hint={
            completion === 100
              ? t("dashboard:candidate.stats.profileHintComplete")
              : t("dashboard:candidate.stats.profileHintIncomplete")
          }
        />
      </dl>
    </header>
  );
}

// ─── Stat ─────────────────────────────────────────────────────────────────

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="bg-card p-4 sm:p-5">
      <dt className="text-[10px] font-medium uppercase tracking-widest text-white/40">
        {label}
      </dt>
      <dd className="mt-1 font-wordmark text-3xl text-copper sm:text-4xl">
        {value}
      </dd>
      {hint && <p className="mt-1 text-xs text-white/40">{hint}</p>}
    </div>
  );
}
