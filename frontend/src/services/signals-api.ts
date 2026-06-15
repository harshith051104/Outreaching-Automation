import api from "./api";

export interface Signal {
  id?: string;
  lead_id: string;
  company_name: string;
  signal_type: string;
  description: string;
  url_source: string;
  signal: string;
  category: string;
  score: number;
  hook: string;
  published_at?: string;
  signal_freshness_score: number;
  created_at?: string;
}

export interface Opportunity {
  lead_id: string;
  urgency: "High" | "Medium" | "Low";
  best_contact: string;
  recommended_offer: string;
  confidence_score: number;
  reasoning: string;
  created_at?: string;
  lead?: {
    id: string;
    name: string;
    email: string;
    company: string;
    role: string;
  };
}

export const getSignals = async (): Promise<Signal[]> => {
  const response = await api.get<{ status: string; signals: Signal[] }>("/signals");
  return response.data.signals || [];
};

export const getLeadSignals = async (leadId: string): Promise<Signal[]> => {
  const response = await api.get<{ status: string; signals: Signal[] }>(`/signals/lead/${leadId}`);
  return response.data.signals || [];
};

export const gatherSignals = async (data: {
  lead_id: string;
  company_name: string;
  website_url?: string;
}): Promise<Signal[]> => {
  const response = await api.post<{ status: string; count: number; signals: Signal[] }>("/signals/gather", data);
  return response.data.signals || [];
};

export const evaluateOpportunity = async (leadId: string): Promise<Opportunity> => {
  const response = await api.post<{ status: string; opportunity: Opportunity }>("/signals/opportunity", {
    lead_id: leadId,
  });
  return response.data.opportunity;
};

export const getOpportunity = async (leadId: string): Promise<Opportunity> => {
  const response = await api.get<{ status: string; opportunity: Opportunity }>(`/signals/opportunity/lead/${leadId}`);
  return response.data.opportunity;
};

export const getAllOpportunities = async (): Promise<Opportunity[]> => {
  const response = await api.get<{ status: string; opportunities: Opportunity[] }>("/signals/opportunities");
  return response.data.opportunities || [];
};
