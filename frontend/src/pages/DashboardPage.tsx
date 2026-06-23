import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import AdminInbox from "@/components/admin/AdminInbox";
import AdminStats from "@/components/admin/AdminStats";
import CandidateDashboard from "@/components/dashboard/CandidateDashboard";
import Eyebrow from "@/components/ui/Eyebrow";
import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/api";

function getGreetingKey(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "dashboard:greeting.morning";
  if (hour < 17) return "dashboard:greeting.afternoon";
  if (hour < 22) return "dashboard:greeting.evening";
  return "dashboard:greeting.night";
}

function formatToday(): string {
  return new Date().toLocaleDateString("he-IL", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/**
 * Pull a display name from the user's email — everything before the `@`,
 * with dots / underscores normalised to a friendlier form.
 */
function nameFromEmail(email: string | undefined): string {
  if (!email) return "";
  const local = email.split("@")[0];
  return local.replace(/[._-]/g, " ");
}

export default function DashboardPage() {
  const { t } = useTranslation('dashboard');
  const { user } = useAuth();
  const isAdmin = user?.role === UserRole.ADMIN;
  const isCandidate = user?.role === UserRole.CANDIDATE;

  const greeting = t(getGreetingKey());
  const name = nameFromEmail(user?.email);
  const today = formatToday();

  const heroSubtitleKey = isAdmin
    ? "dashboard:heroSubtitle.admin"
    : isCandidate
      ? "dashboard:heroSubtitle.candidate"
      : "dashboard:heroSubtitle.company";

  return (
    <div>
      {/* Warm, time-aware hero — candidate flow owns its own hero so it
          can use the real CandidateProfile.full_name (fetched alongside
          the dashboard data) instead of the email-prefix shim. */}
      {!isCandidate && (
        <header className="mb-8 border-b border-white/8 pb-6 sm:mb-10 sm:pb-8">
          <Eyebrow>
            {today}
          </Eyebrow>
          <h1 className="mt-3 text-2xl font-semibold text-white/90 sm:text-3xl">
            {greeting}
            {name && <span className="text-copper/85">{`, ${name}`}</span>}
          </h1>
          <p className="mt-2 text-sm text-white/45">{t(heroSubtitleKey)}</p>
        </header>
      )}

      {isAdmin ? (
        <div className="space-y-10">
          <section>
            <AdminInbox />
          </section>
          <section>
            <AdminStats />
          </section>
          <section>
            <QuickActions />
          </section>
        </div>
      ) : isCandidate ? (
        <CandidateDashboard />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Link
            to="/company/jobs"
            className="group rounded-xl border border-white/8 bg-card p-5 transition duration-200 hover:border-copper/30 hover:bg-card-raised"
          >
            <p className="font-medium text-white/85 transition group-hover:text-white/95">
              {t("dashboard:companyLinks.myJobs")}
            </p>
            <p className="mt-1 text-sm text-white/45">
              {t("dashboard:companyLinks.myJobsDesc")}
            </p>
          </Link>
        </div>
      )}
    </div>
  );
}

/** Admin call-to-actions: warmer button styles + brief copy. */
function QuickActions() {
  const { t } = useTranslation('dashboard');
  const actions = [
    {
      to: "/admin/companies?view=invites&action=invite",
      label: t("dashboard:quickActions.invite.label"),
      hint: t("dashboard:quickActions.invite.hint"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="size-4" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 7l9 6 9-6M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
        </svg>
      ),
    },
    {
      to: "/admin/companies?view=active",
      label: t("dashboard:quickActions.companies.label"),
      hint: t("dashboard:quickActions.companies.hint"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="size-4" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 21h18M5 21V7l7-4 7 4v14M9 9h.01M13 9h.01M9 13h.01M13 13h.01M9 17h.01M13 17h.01" />
        </svg>
      ),
    },
    {
      to: "/admin/jobs",
      label: t("dashboard:quickActions.jobs.label"),
      hint: t("dashboard:quickActions.jobs.hint"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="size-4" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2ZM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      ),
    },
    {
      to: "/admin/candidates",
      label: t("dashboard:quickActions.candidates.label"),
      hint: t("dashboard:quickActions.candidates.hint"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="size-4" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm14 0a4 4 0 1 0-2-7.5" />
        </svg>
      ),
    },
  ];
  return (
    <div>
      <Eyebrow className="mb-3">
        {t("dashboard:quickActions.title")}
      </Eyebrow>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {actions.map((a) => (
          <Link
            key={a.to}
            to={a.to}
            className="group flex items-start gap-2.5 rounded-lg border border-white/8 bg-card px-3 py-3 transition hover:border-copper/30 hover:bg-card-raised"
          >
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-copper/15 text-copper transition group-hover:bg-copper/25">
              {a.icon}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-white/85">
                {a.label}
              </span>
              <span className="block truncate text-[11px] text-white/40">
                {a.hint}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
