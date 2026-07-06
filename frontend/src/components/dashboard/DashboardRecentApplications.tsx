import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import type { CandidateApplicationListItem } from "@/services/candidate";

function formatRelative(
  iso: string,
  _locale: string,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const submitted = new Date(iso).getTime();
  const now = Date.now();
  const days = Math.max(0, Math.floor((now - submitted) / 86_400_000));
  if (days === 0) return t("candidate:applications.relative.today");
  if (days === 1) return t("candidate:applications.relative.yesterday");
  if (days < 7) return t("candidate:applications.relative.daysAgo", { count: days });
  if (days < 30)
    return t("candidate:applications.relative.weeksAgo", {
      count: Math.floor(days / 7),
    });
  if (days < 365)
    return t("candidate:applications.relative.monthsAgo", {
      count: Math.floor(days / 30),
    });
  return t("candidate:applications.relative.yearsAgo", {
    count: Math.floor(days / 365),
  });
}

export function RecentApplications({
  items,
}: {
  items: CandidateApplicationListItem[] | null;
}) {
  const { t, i18n } = useTranslation(["candidate", "dashboard"]);

  if (items === null) {
    return (
      <section>
        <Eyebrow className="mb-3">
          {t("dashboard:candidate.recentApplications.title")}
        </Eyebrow>
        <ul className="space-y-2">
          {[0, 1, 2].map((i) => (
            <li
              key={i}
              className="h-16 animate-pulse rounded-xl border border-white/8 bg-card"
            />
          ))}
        </ul>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <Eyebrow>{t("dashboard:candidate.recentApplications.title")}</Eyebrow>
        {items.length > 0 && (
          <Link
            to="/candidate/applications"
            className="text-xs text-white/50 transition hover:text-white/85"
          >
            {t("dashboard:candidate.recentApplications.viewAll")}
          </Link>
        )}
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-white/8 bg-card-raised p-10 text-center">
          <span className="flex size-14 items-center justify-center rounded-full border border-copper/25 bg-copper/8 text-copper">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="size-6"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 7h18M3 7l1.5 12.5A2 2 0 0 0 6.5 21h11a2 2 0 0 0 2-1.5L21 7M3 7l2-4h14l2 4M9 11v6m6-6v6"
              />
            </svg>
          </span>
          <p className="max-w-xs text-sm text-white/65">
            {t("dashboard:candidate.recentApplications.empty")}
          </p>
          <Link
            to="/jobs"
            className="mt-1 inline-flex items-center gap-2 rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("dashboard:candidate.recentApplications.browseCta")}
            <IconArrow />
          </Link>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((row) => (
            <li key={row.id}>
              <Link
                to={`/candidate/applications/${row.id}`}
                className="block rounded-xl border border-white/8 bg-card p-4 transition hover:border-white/20 hover:bg-card-raised"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm font-medium text-copper">
                    {row.job.title}
                  </span>
                  <span className="shrink-0 text-[11px] text-white/45">
                    {formatRelative(row.submitted_at, i18n.language, t)}
                  </span>
                </div>
                {row.job.closed && (
                  <span className="mt-2 inline-block rounded-sm border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-widest text-white/45">
                    {t("candidate:applications.closedPill")}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function IconArrow() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className="size-4"
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m0 0-5-5m5 5-5 5" />
    </svg>
  );
}
