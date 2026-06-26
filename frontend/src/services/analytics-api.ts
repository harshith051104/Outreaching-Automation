import api from "./api";
import type { DashboardStats, CampaignAnalytics, DailyStats } from "@/types/analytics";

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await api.get<DashboardStats>("/analytics/dashboard");
  return response.data;
};

export const getCampaignAnalytics = async (id: string): Promise<CampaignAnalytics> => {
  const response = await api.get<CampaignAnalytics>(`/analytics/campaign/${id}`);
  return response.data;
};

export const getDailyStats = async (id: string): Promise<DailyStats[]> => {
  const response = await api.get<DailyStats[]>(`/analytics/campaign/${id}/daily`);
  return response.data;
};

export const getCampaignInsights = async (id: string): Promise<{ insights: string[] }> => {
  const response = await api.get<{ insights: string[] }>(`/analytics/campaign/${id}/insights`);
  return response.data;
};

export const getGlobalAiInsights = async (): Promise<any> => {
  const response = await api.get("/analytics/ai-insights");
  return response.data;
};

export const exportDashboardToSheets = async (): Promise<{ success: boolean; spreadsheet_url: string; title: string }> => {
  const response = await api.post<{ success: boolean; spreadsheet_url: string; title: string }>(
    "/analytics/dashboard/export/sheets",
    null
  );
  return response.data;
};

export const exportCampaignAnalyticsToSheets = async (
  id: string,
  days = 30
): Promise<{ success: boolean; spreadsheet_url: string; title: string }> => {
  const response = await api.post<{ success: boolean; spreadsheet_url: string; title: string }>(
    `/analytics/campaign/${id}/export/sheets`,
    null,
    { params: { days } }
  );
  return response.data;
};