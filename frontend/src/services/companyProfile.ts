/**
 * Company self-service profile and stats API.
 * All endpoints require COMPANY role JWT.
 */
import api from "@/services/api";
import type { CompanyProfileRead, CompanyProfileSelfUpdate, CompanyStats } from "@/types/companies";

export async function getMyCompanyProfile(): Promise<CompanyProfileRead> {
  const res = await api.get<CompanyProfileRead>("/api/companies/me");
  return res.data;
}

export async function updateMyCompanyProfile(
  data: CompanyProfileSelfUpdate,
): Promise<CompanyProfileRead> {
  const res = await api.patch<CompanyProfileRead>("/api/companies/me", data);
  return res.data;
}

export async function getMyCompanyStats(): Promise<CompanyStats> {
  const res = await api.get<CompanyStats>("/api/companies/me/stats");
  return res.data;
}
