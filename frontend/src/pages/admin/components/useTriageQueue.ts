import { useCallback, useEffect, useState } from "react";

import { getApplications } from "@/services/adminApplications";
import { getActiveCompanies } from "@/services/adminCompanies";
import type { ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";

/**
 * One candidate ready for triage — `ApplicationWithDetails` plus the resolved
 * company name (the API only returns `company_id` on the job).
 */
export interface TriageItem extends ApplicationWithDetails {
  companyName: string;
}

interface State {
  items: TriageItem[];
  isLoading: boolean;
  error: Error | null;
}

/**
 * Fetches the NEW-applications queue + the active-companies list so company
 * names can be inlined onto each item. Single batched load (limit 200) —
 * the triage UX expects to know the full queue upfront for the strip viz.
 *
 * Returns a stable `reload` callback for the error/refresh paths.
 */
export function useTriageQueue() {
  const [state, setState] = useState<State>({
    items: [],
    isLoading: true,
    error: null,
  });

  /** Run the fetch and write the result to state. Does NOT toggle isLoading
   *  itself — callers (the mount effect / `reload`) are responsible for that
   *  so the lint rule against setState-in-effect is respected.
   *
   *  Backend caps `limit` at 100 (MAX_LIMIT in pagination.py), so we loop
   *  through cursor pages up to MAX_PAGES to support larger queues. With the
   *  page-size cap that's 500 total — plenty for any plausible NEW queue.
   */
  const fetchInto = useCallback(async (signal?: AbortSignal) => {
    const PAGE_SIZE = 100;
    const MAX_PAGES = 5;
    try {
      const apps: TriageItem[] = [];
      // We need the full list, so iterate cursor pages serially.
      // Companies can be fetched in parallel with the first apps page.
      const [firstAppsPage, companiesPage] = await Promise.all([
        getApplications({ status: ApplicationStatus.NEW, limit: PAGE_SIZE }, signal),
        getActiveCompanies({ limit: PAGE_SIZE }, signal),
      ]);

      const companyNameById = new Map(
        companiesPage.items.map((c) => [c.company_profile.id, c.company_profile.name]),
      );
      const toTriageItem = (app: ApplicationWithDetails): TriageItem => ({
        ...app,
        companyName: companyNameById.get(app.job.company_id) ?? "—",
      });

      apps.push(...firstAppsPage.items.map(toTriageItem));
      let cursor = firstAppsPage.next_cursor;
      for (let i = 1; i < MAX_PAGES && cursor; i++) {
        const page = await getApplications(
          { status: ApplicationStatus.NEW, limit: PAGE_SIZE, cursor },
          signal,
        );
        apps.push(...page.items.map(toTriageItem));
        cursor = page.next_cursor;
      }

      setState({ items: apps, isLoading: false, error: null });
    } catch (err: unknown) {
      if (signal?.aborted) return;
      setState({
        items: [],
        isLoading: false,
        error: err instanceof Error ? err : new Error("Failed to load queue"),
      });
    }
  }, []);

  useEffect(() => {
    // `isLoading` is initialised true above, so the first fetch doesn't need
    // a synchronous setState to flip it. `fetchInto` is async — every setState
    // inside it runs after an await — so the rule's concern (sync cascading
    // renders) doesn't apply. Disable for this known-safe call.
    const ctrl = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchInto(ctrl.signal);
    return () => ctrl.abort();
  }, [fetchInto]);

  const reload = useCallback(() => {
    setState((s) => ({ ...s, isLoading: true, error: null }));
    return fetchInto();
  }, [fetchInto]);

  return {
    items: state.items,
    isLoading: state.isLoading,
    error: state.error,
    reload,
  };
}
