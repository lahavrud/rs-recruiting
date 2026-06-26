import api from "@/services/api";

export interface AdminInboxCounts {
  pending_invites: number;
  pending_companies: number;
  pending_jobs: number;
  new_applications: number;
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

export interface AdminOverviewRead {
  inbox: AdminInboxCounts;
  stats: AdminStatsCounts;
}

export async function getAdminOverview(signal?: AbortSignal): Promise<AdminOverviewRead> {
  const res = await api.get<AdminOverviewRead>("/api/admin/overview", { signal });
  return res.data;
}
