import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import AdminHotApplicationsFeed from "@/components/admin/AdminHotApplicationsFeed";
import AdminInbox from "@/components/admin/AdminInbox";
import AdminMatchFeed from "@/components/admin/AdminMatchFeed";
import AdminRecentFeed from "@/components/admin/AdminRecentFeed";
import AdminStats from "@/components/admin/AdminStats";
import CandidateDashboard from "@/components/dashboard/CandidateDashboard";
import Eyebrow from "@/components/ui/Eyebrow";
import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/enums";
import { formatTodayHebrew } from "@/utils/formatDate";

function getGreetingKey(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "dashboard:greeting.morning";
  if (hour < 17) return "dashboard:greeting.afternoon";
  if (hour < 22) return "dashboard:greeting.evening";
  return "dashboard:greeting.night";
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
  const { t } = useTranslation("dashboard");
  const { user } = useAuth();
  const isAdmin = user?.role === UserRole.ADMIN;
  const isCandidate = user?.role === UserRole.CANDIDATE;

  const greeting = t(getGreetingKey());
  const name = isAdmin ? "" : nameFromEmail(user?.email);
  const today = formatTodayHebrew();

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
          <Eyebrow>{today}</Eyebrow>
          <h1 className="mt-3 text-2xl font-semibold text-white/90 sm:text-3xl">
            {greeting}
            {name && <span className="text-copper/85">{`, ${name}`}</span>}
          </h1>
          <p className="mt-2 text-sm text-white/45">{t(heroSubtitleKey)}</p>
        </header>
      )}

      {isAdmin ? (
        <div className="space-y-8 sm:space-y-10">
          <section>
            <AdminInbox />
          </section>
          <section>
            <AdminStats />
          </section>
          <section>
            <AdminHotApplicationsFeed />
          </section>
          <section>
            <AdminMatchFeed />
          </section>
          <section>
            <AdminRecentFeed />
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

