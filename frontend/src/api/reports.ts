import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { ReportGenerateRequest, ReportJob } from "@/types/teacherReview";

/** Background report generation (Module 07, Feature 8, ADR-045). See
 * `backend/app/api/v1/endpoints/reports.py`. */
export async function listReports(params?: PageParams): Promise<Page<ReportJob>> {
  const { data } = await apiClient.get<Page<ReportJob>>("/reports", { params });
  return data;
}

export async function getReport(id: string): Promise<ReportJob> {
  const { data } = await apiClient.get<ReportJob>(`/reports/${id}`);
  return data;
}

export async function generateReport(payload: ReportGenerateRequest): Promise<ReportJob> {
  const { data } = await apiClient.post<ReportJob>("/reports", payload);
  return data;
}

export async function downloadReport(id: string): Promise<{ url: string }> {
  const { data } = await apiClient.get<{ url: string }>(`/reports/${id}/download`);
  return data;
}
