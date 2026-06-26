import api from "@/services/api";

export interface AdminInboxCounts {
  pending_invites: number;
  pending_companies: number;
  pending_jobs: number;
  new_applications: number;
  oldest_pending_company_days: number | null;
  oldest_pending_job_days: number | null;
  oldest_new_application_days: number | null;
}

export interface TopJobEntry {
  id: number;
  title: string;
  application_count: number;
}

export interface AdminStatsCounts {
  active_companies: number;
  published_jobs: number;
  total_candidates: number;
  application_status_counts: Record<string, number>;
  top_jobs: TopJobEntry[];
}

export interface RecentItem {
  type: "company" | "job" | "application";
  label: string;
  sublabel: string | null;
  created_at: string;
}

export interface TrendPoint {
  date: string;
  n: number;
}

export interface AdminPulse {
  new_candidates_7d: number;
  new_applications_7d: number;
  recent_items: RecentItem[];
  trend_30d: TrendPoint[];
}

export interface AdminOverviewRead {
  inbox: AdminInboxCounts;
  stats: AdminStatsCounts;
  pulse: AdminPulse;
}

export async function getAdminOverview(signal?: AbortSignal): Promise<AdminOverviewRead> {
  const res = await api.get<AdminOverviewRead>("/api/admin/overview", { signal });
  return res.data;
}
