import { getAdminOverview, type AdminOverviewRead } from "@/services/adminOverview";

import { useFetch, type UseFetchResult } from "./useFetch";

/**
 * Shared, deduplicated read layer for `GET /api/admin/overview`.
 *
 * The overview payload (`{ inbox, stats, pulse }`) is consumed by several admin
 * surfaces at once — the layout Sidebar plus the dashboard widgets (AdminStats,
 * AdminRecentFeed, AdminInbox) all mount in the same commit. Each used to run
 * its own `getAdminOverview()` in a `useEffect`, firing N concurrent identical
 * requests per page load, each re-running the full server-side aggregation
 * (#1051).
 *
 * `getAdminOverviewShared` collapses that by sharing a single in-flight request
 * across concurrent callers. It deliberately does NOT cache the resolved
 * payload: once the request settles the in-flight handle clears, so a later
 * mount (a fresh navigation) fetches fresh — matching the previous
 * per-component behaviour, just without the mount-storm. Not caching also means
 * no post-mutation staleness window and nothing that outlives the session.
 *
 * The shared fetch takes no AbortSignal: it is not owned by any single
 * consumer, so one component unmounting must not cancel the request the others
 * are still waiting on. `useFetch`'s alive-guard drops late results per
 * consumer instead.
 */
let inFlight: Promise<AdminOverviewRead> | null = null;

export function getAdminOverviewShared(): Promise<AdminOverviewRead> {
  if (inFlight != null) return inFlight;
  inFlight = getAdminOverview().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/** Drop any in-flight shared request. For tests and hard refreshes. */
export function resetAdminOverviewShared(): void {
  inFlight = null;
}

/**
 * Subscribe to the shared admin-overview read. Pass `enabled=false` to skip the
 * fetch entirely (e.g. the Sidebar renders for every role but only admins may
 * hit the endpoint). Consumers read whichever slice they need off `data` and
 * treat `data == null` as the loading/placeholder state, matching the previous
 * per-component behaviour.
 */
export function useAdminOverview(enabled = true): UseFetchResult<AdminOverviewRead> {
  return useFetch(getAdminOverviewShared, [], enabled);
}
