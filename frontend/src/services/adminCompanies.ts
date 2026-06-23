import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type {
  CompanyProfileAdminCreate,
  CompanyProfileAdminUpdate,
  CompanyProfileRead,
} from "@/types/auth";
import type {
  ActiveCompanyRead,
  ApprovedCompanyRead,
  PendingCompanyRead,
} from "@/types/companies";

export interface PendingCompaniesParams {
  cursor?: string | null;
  limit?: number;
}

export interface ActiveCompaniesParams {
  cursor?: string | null;
  limit?: number;
}

export async function getPendingCompanies(
  params?: PendingCompaniesParams,
  signal?: AbortSignal,
): Promise<CursorPage<PendingCompanyRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<PendingCompanyRead>>(
    "/api/admin/companies/pending",
    { params: query, signal },
  );
  return res.data;
}

export async function approveCompany(userId: number): Promise<ApprovedCompanyRead> {
  const res = await api.post<ApprovedCompanyRead>(
    `/api/admin/companies/${userId}/approve`,
  );
  return res.data;
}

export async function rejectCompany(userId: number): Promise<void> {
  await api.post(`/api/admin/companies/${userId}/reject`);
}

export async function getActiveCompanies(
  params?: ActiveCompaniesParams,
  signal?: AbortSignal,
): Promise<CursorPage<ActiveCompanyRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<ActiveCompanyRead>>("/api/admin/companies", {
    params: query,
    signal,
  });
  return res.data;
}

export async function deleteCompany(userId: number): Promise<void> {
  await api.delete(`/api/admin/companies/${userId}`);
}

export async function deleteOrphanCompany(profileId: number): Promise<void> {
  await api.delete(`/api/admin/companies/profile/${profileId}`);
}

export async function adminCreateCompany(
  body: CompanyProfileAdminCreate,
): Promise<CompanyProfileRead> {
  const res = await api.post<CompanyProfileRead>("/api/admin/companies", body);
  return res.data;
}

export async function getCompanyProfile(
  profileId: number,
  signal?: AbortSignal,
): Promise<CompanyProfileRead> {
  const res = await api.get<CompanyProfileRead>(
    `/api/admin/companies/profile/${profileId}`,
    { signal },
  );
  return res.data;
}

export async function updateCompanyProfile(
  profileId: number,
  body: CompanyProfileAdminUpdate,
): Promise<CompanyProfileRead> {
  const res = await api.put<CompanyProfileRead>(
    `/api/admin/companies/profile/${profileId}`,
    body,
  );
  return res.data;
}
