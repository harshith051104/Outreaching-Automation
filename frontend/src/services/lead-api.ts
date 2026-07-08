import api from "./api";
import type { Lead, LeadCreate } from "@/types/lead";

export const getLeads = async (campaignId?: string, limit: number = 200): Promise<Lead[]> => {
  const params: any = { limit };
  if (campaignId) params.campaign_id = campaignId;
  const response = await api.get<Lead[]>("/leads", { params });
  return response.data;
};

export const getLead = async (id: string): Promise<Lead> => {
  const response = await api.get<Lead>(`/leads/${id}`);
  return response.data;
};

export const createLead = async (data: LeadCreate): Promise<Lead> => {
  const response = await api.post<Lead>("/leads", data);
  return response.data;
};

export const updateLead = async (id: string, data: Partial<LeadCreate>): Promise<Lead> => {
  const response = await api.patch<Lead>(`/leads/${id}`, data);
  return response.data;
};

export const deleteLead = async (id: string): Promise<void> => {
  await api.delete(`/leads/${id}`);
};

export const uploadLeadCsv = async (campaignId: string, file: File): Promise<{ imported: number; skipped: number; errors: string[] }> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post<{ imported: number; skipped: number; errors: string[] }>(
    `/leads/upload-csv?campaign_id=${campaignId}`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return response.data;
};

export const getLeadEngagement = async (id: string): Promise<Record<string, unknown>> => {
  const response = await api.get(`/leads/${id}/engagement`);
  return response.data;
};

export const getLeadSignals = async (leadId: string): Promise<{ status: string; signals: any[] }> => {
  const response = await api.get<{ status: string; signals: any[] }>(`/signals/lead/${leadId}`);
  return response.data;
};

export const evaluateLeadOpportunity = async (leadId: string): Promise<{ status: string; opportunity: any }> => {
  const response = await api.post<{ status: string; opportunity: any }>("/signals/opportunity", { lead_id: leadId });
  return response.data;
};

export const getLeadOpportunity = async (leadId: string): Promise<{ status: string; opportunity: any }> => {
  const response = await api.get<{ status: string; opportunity: any }>(`/signals/opportunity/lead/${leadId}`);
  return response.data;
};

export const importGoogleSheet = async (campaignId: string, url: string): Promise<{ imported: number; skipped: number; errors: string[] }> => {
  const response = await api.post<{ imported: number; skipped: number; errors: string[] }>("/leads/import-google-sheet", {
    campaign_id: campaignId,
    url
  });
  return response.data;
};