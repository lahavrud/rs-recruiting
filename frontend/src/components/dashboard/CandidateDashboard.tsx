import { useEffect, useState } from "react";

import {
  getMe,
  listMyApplications,
  type CandidateApplicationsPage,
  type CandidateMeRead,
} from "@/services/candidate";

import { BrowseJobsCta } from "./DashboardBrowseJobsCta";
import { Hero } from "./DashboardHero";
import { ProfileCompletion } from "./DashboardProfileCompletion";
import { RecentApplications } from "./DashboardRecentApplications";

/**
 * Candidate dashboard.
 *
 * Owns its own hero so it can use the real ``CandidateProfile.full_name``
 * (only available after the /api/candidate/me fetch) instead of the
 * email-local-part shim DashboardPage uses for admin/company.
 *
 * Sections, ordered by what's actionable:
 *   1. Hero with greeting + at-a-glance stats (applications submitted,
 *      profile completion %).
 *   2. Profile completion strip — filled chips (✓) alongside missing
 *      chips (+) so the candidate sees progress, not just a hole.
 *   3. Recent applications — last 3 rows.
 *   4. Browse jobs CTA — copper-tinted card.
 *
 * Both API calls are fired in parallel via ``Promise.allSettled`` — one
 * failing leaves a graceful skeleton/empty state on its own block.
 */
export default function CandidateDashboard() {
  const [me, setMe] = useState<CandidateMeRead | null>(null);
  const [appsPage, setAppsPage] = useState<CandidateApplicationsPage | null>(
    null,
  );

  useEffect(() => {
    let alive = true;
    void Promise.allSettled([getMe(), listMyApplications()]).then(
      ([meResult, appsResult]) => {
        if (!alive) return;
        if (meResult.status === "fulfilled") setMe(meResult.value);
        if (appsResult.status === "fulfilled") setAppsPage(appsResult.value);
        else setAppsPage({ items: [], next_cursor: null });
      },
    );
    return () => {
      alive = false;
    };
  }, []);

  const apps = appsPage?.items?.slice(0, 3) ?? null;

  return (
    <div className="space-y-8">
      <Hero me={me} appsPage={appsPage} />
      <ProfileCompletion me={me} onMeChange={setMe} />
      <RecentApplications items={apps} />
      <BrowseJobsCta hasApps={(appsPage?.items?.length ?? 0) > 0} />
    </div>
  );
}
