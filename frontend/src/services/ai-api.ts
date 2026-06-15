import api from "./api";

export interface GenerateEmailRequest {
  lead_id: string;
  campaign_id: string;
  tone?: string;
}

export interface ResearchLeadRequest {
  lead_id: string;
}

export interface ClassifyReplyRequest {
  reply_text: string;
  email_id: string;
}

export interface GenerateFollowupRequest {
  lead_id: string;
  campaign_id: string;
  previous_email_id: string;
}

export interface CampaignInsightsRequest {
  campaign_id: string;
}

export const aiApi = {
  async generateEmail(data: GenerateEmailRequest): Promise<{ subject: string; body: string }> {
    const response = await api.post<{ subject: string; body: string }>("/ai/generate-email", data);
    return response.data;
  },

  async researchLead(data: ResearchLeadRequest): Promise<{ research: Record<string, unknown> }> {
    const response = await api.post<{ research: Record<string, unknown> }>("/ai/research-lead", data);
    return response.data;
  },

  async classifyReply(data: ClassifyReplyRequest): Promise<{
    classification: string;
    sentiment: string;
    confidence: number;
  }> {
    const response = await api.post("/ai/classify-reply", data);
    return response.data;
  },

  async generateFollowup(data: GenerateFollowupRequest): Promise<{ subject: string; body: string }> {
    const response = await api.post<{ subject: string; body: string }>("/ai/generate-followup", data);
    return response.data;
  },

  async campaignInsights(data: CampaignInsightsRequest): Promise<{ insights: string[]; recommendations: string[] }> {
    const response = await api.post<{ insights: string[]; recommendations: string[] }>("/ai/campaign-insights", data);
    return response.data;
  },

  async retrieveMemory(query: string, limit?: number, campaignId?: string): Promise<{
    status: string;
    results: {
      successful_emails: any[];
      past_replies: any[];
    }
  }> {
    const params = { query, limit, campaign_id: campaignId };
    const response = await api.get<{
      status: string;
      results: {
        successful_emails: any[];
        past_replies: any[];
      }
    }>("/ai/memory", { params });
    return response.data;
  },
};
