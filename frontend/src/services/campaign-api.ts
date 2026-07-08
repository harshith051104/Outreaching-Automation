import api from "./api";
import type { Campaign, CampaignCreate } from "@/types/campaign";
import type { CampaignAnalytics } from "@/types/analytics";

export const getCampaigns = async (limit: number = 100): Promise<Campaign[]> => {
  const response = await api.get<Campaign[]>("/campaigns", { params: { limit } });
  return response.data;
};

export const getCampaign = async (id: string): Promise<Campaign> => {
  const response = await api.get<Campaign>(`/campaigns/${id}`);
  return response.data;
};

export const createCampaign = async (data: CampaignCreate): Promise<Campaign> => {
  const response = await api.post<Campaign>("/campaigns", data);
  return response.data;
};

export const updateCampaign = async (id: string, data: Partial<CampaignCreate>): Promise<Campaign> => {
  const response = await api.put<Campaign>(`/campaigns/${id}`, data);
  return response.data;
};

export const startCampaign = async (id: string): Promise<Campaign> => {
  const response = await api.post<Campaign>(`/campaigns/${id}/start`);
  return response.data;
};

export const pauseCampaign = async (id: string): Promise<Campaign> => {
  const response = await api.post<Campaign>(`/campaigns/${id}/pause`);
  return response.data;
};

export const getCampaignStats = async (id: string): Promise<CampaignAnalytics> => {
  const response = await api.get<CampaignAnalytics>(`/campaigns/${id}/stats`);
  return response.data;
};

export const deleteCampaign = async (id: string): Promise<void> => {
  await api.delete(`/campaigns/${id}`);
};

export const clearAICache = async (campaignId: string, leadId: string): Promise<void> => {
  await api.delete(`/campaigns/${campaignId}/ai-cache/${leadId}`);
};