import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import StatusBadge from "@/components/ui/StatusBadge";
import { getAdminOverview, type RecentItem } from "@/services/adminOverview";
import { formatTimeAgo } from "@/utils/formatDate";

const RECENT_URL: Record<RecentItem["type"], string> = {
  company: "/admin/companies?view=pending",
  job: "/admin/jobs?status=PENDING_APPROVAL",
  application: "/admin/applications?status=NEW",
};

export default function AdminRecentFeed() {
  const { t } = useTranslation("dashboard");
  const [items, setItems] = useState<RecentItem[] | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then((data) => setItems(data.pulse.recent_items))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  const isEmpty = items != null && items.length === 0;

  return (
    <div>
      <div className="mb-3">
        <Eyebrow>{t("dashboard:recent.title")}</Eyebrow>
      </div>

      <div className="rounded-xl border border-white/8 bg-card">
        {items == null ? (
          <div className="space-y-px">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3">
                <div className="size-7 animate-pulse rounded-full bg-white/8" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-2.5 w-1/2 animate-pulse rounded bg-white/8" />
                  <div className="h-2 w-1/3 animate-pulse rounded bg-white/6" />
                </div>
              </div>
            ))}
          </div>
        ) : isEmpty ? (
          <p className="px-4 py-5 text-sm text-white/35">{t("dashboard:recent.empty")}</p>
        ) : (
          <ul>
            {items.map((item, i) => (
              <li
                key={`${item.type}-${item.created_at}-${i}`}
                className={i < items.length - 1 ? "border-b border-white/6" : ""}
              >
                <Link
                  to={RECENT_URL[item.type]}
                  className="group flex items-center gap-3 px-4 py-3 transition hover:bg-card-raised"
                >
                  <TypeIcon type={item.type} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white/85 transition group-hover:text-white/95">
                      {item.label}
                    </p>
                    {item.sublabel && (
                      <p className="truncate text-xs text-white/40">{item.sublabel}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-white/30">
                      {formatTimeAgo(item.created_at)}
                    </span>
                    <StatusBadge
                      variant={item.type === "company" ? "info" : item.type === "job" ? "copper" : "success"}
                      label={t(`dashboard:recent.types.${item.type}`)}
                    />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function TypeIcon({ type }: { type: RecentItem["type"] }) {
  if (type === "company") {
    return (
      <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-info/10 text-info/70">
        <svg viewBox="0 0 16 16" fill="currentColor" className="size-3.5" aria-hidden="true">
          <path
            fillRule="evenodd"
            d="M1 2.5A1.5 1.5 0 0 1 2.5 1h11A1.5 1.5 0 0 1 15 2.5v11a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 13.5v-11ZM5 4a1 1 0 0 0-1 1v1a1 1 0 0 0 2 0V5a1 1 0 0 0-1-1Zm5 0a1 1 0 0 0-1 1v1a1 1 0 0 0 2 0V5a1 1 0 0 0-1-1ZM5 9a1 1 0 0 0-1 1v1a1 1 0 0 0 2 0v-1a1 1 0 0 0-1-1Zm5 0a1 1 0 0 0-1 1v1a1 1 0 0 0 2 0v-1a1 1 0 0 0-1-1Z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    );
  }
  if (type === "job") {
    return (
      <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-copper/10 text-copper/70">
        <svg viewBox="0 0 16 16" fill="currentColor" className="size-3.5" aria-hidden="true">
          <path d="M6.5 1A1.5 1.5 0 0 0 5 2.5V3H2.5A1.5 1.5 0 0 0 1 4.5v8A1.5 1.5 0 0 0 2.5 14h11a1.5 1.5 0 0 0 1.5-1.5v-8A1.5 1.5 0 0 0 13.5 3H11v-.5A1.5 1.5 0 0 0 9.5 1h-3ZM6 2.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 .5.5V3H6v-.5Z" />
        </svg>
      </span>
    );
  }
  return (
    <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-success/10 text-success/70">
      <svg viewBox="0 0 16 16" fill="currentColor" className="size-3.5" aria-hidden="true">
        <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4Z" />
      </svg>
    </span>
  );
}

