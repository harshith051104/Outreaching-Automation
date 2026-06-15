/**
 * LinkedIn Outreach API Service
 * 
 * Typed interfaces and API calls for the LinkedIn Outreach module.
 * Covers: session management, research, outreach, campaigns, conversations, analytics.
 */

import api from "./api";

// ── Interfaces ────────────────────────────────────────────────────────────

export interface LinkedInSessionStatus {
  status: "connected" | "disconnected" | "expired" | "error";
  last_validated_at?: string;
  created_at?: string;
  message?: string;
  account_name?: string;
  profile_url?: string;
  avatar_url?: string;
}

export interface LinkedInProfileData {
  name: string;
  headline: string;
  about: string;
  location: string;
  experience: Array<{ title: string; company: string; duration: string }>;
  education: Array<{ school: string; degree: string; field: string }>;
  skills: string[];
  connection_count: string;
  profile_url: string;
}

export interface LinkedInAction {
  id: string;
  user_id: string;
  lead_id?: string;
  linkedin_url: string;
  action_type: string;
  status: "pending_approval" | "scheduled" | "executed" | "failed" | "rejected";
  message: string;
  profile_data?: LinkedInProfileData;
  research_data?: Record<string, unknown>;
  created_at: string;
  executed_at?: string;
  execution_result?: {
    error?: string;
    error_screenshot?: string;
    [key: string]: unknown;
  };
  error?: string;
  message_skipped?: boolean;
}

export interface LinkedInCampaign {
  id: string;
  user_id: string;
  name: string;
  description: string;
  goal: string;
  target_audience: string;
  status: "draft" | "active" | "paused" | "completed";
  daily_connection_limit: number;
  daily_message_limit: number;
  total_planned_actions: number;
  executed_actions: number;
  created_at: string;
  updated_at: string;
}

export interface LinkedInConversation {
  id?: string;
  user_id: string;
  contact_linkedin_url: string;
  contact_name: string;
  last_message_preview: string;
  last_message_at: string;
  has_unread: boolean;
}

export interface LinkedInRelationship {
  id: string;
  user_id: string;
  linkedin_url: string;
  lead_id?: string;
  contact_name?: string;
  first_name?: string;
  last_name?: string;
  current_stage: string;
  stage_history: Array<{ from_stage?: string; to_stage?: string; stage?: string; timestamp: string }>;
  created_at: string;
  updated_at: string;
}

export interface LinkedInMetrics {
  connections_sent: number;
  connections_accepted: number;
  acceptance_rate: number;
  messages_sent: number;
  replies_received: number;
  reply_rate: number;
  followups_sent: number;
  meetings_booked: number;
  opportunities_created: number;
}

export interface LinkedInAnalytics {
  metrics: LinkedInMetrics;
  insights: string[];
  recommendations: string[];
  top_performing_messages: Array<{ message_preview: string; acceptance_rate: number }>;
}

export interface LinkedInQueueStatus {
  pending_approval: number;
  scheduled: number;
  executed_total: number;
  failed_total: number;
  daily_connections: { used: number; max: number; remaining: number };
  daily_messages: { used: number; max: number; remaining: number };
}

// ── Session ───────────────────────────────────────────────────────────────

export const connectLinkedInSession = async (): Promise<LinkedInSessionStatus> => {
  const response = await api.post<LinkedInSessionStatus>("/linkedin/session/connect");
  return response.data;
};

export const getLinkedInSessionStatus = async (): Promise<LinkedInSessionStatus> => {
  const response = await api.get<LinkedInSessionStatus>("/linkedin/session/status");
  return response.data;
};

export const disconnectLinkedInSession = async (): Promise<LinkedInSessionStatus> => {
  const response = await api.post<LinkedInSessionStatus>("/linkedin/session/disconnect");
  return response.data;
};

export const validateLinkedInSession = async (): Promise<LinkedInSessionStatus> => {
  const response = await api.post<LinkedInSessionStatus>("/linkedin/session/validate");
  return response.data;
};

// ── Research ──────────────────────────────────────────────────────────────

export const researchLinkedInProfile = async (
  linkedin_url: string,
  outreach_type: string = "connection_request"
): Promise<{ profile_data: LinkedInProfileData; research_data: Record<string, unknown>; personalization_data: Record<string, unknown> }> => {
  const response = await api.post("/linkedin/research", { linkedin_url, outreach_type });
  return response.data;
};

// ── Outreach ──────────────────────────────────────────────────────────────

export const createConnectionRequest = async (
  linkedin_url: string,
  lead_id: string = "",
  custom_note: string = ""
): Promise<{ action_id: string; draft_message: string; profile_data?: LinkedInProfileData; status: string }> => {
  const response = await api.post("/linkedin/outreach/connection", {
    linkedin_url,
    lead_id,
    custom_note,
  });
  return response.data;
};

export const createFollowRequest = async (
  linkedin_url: string,
  lead_id: string = ""
): Promise<{ action_id: string; status: string }> => {
  const response = await api.post("/linkedin/outreach/follow", {
    linkedin_url,
    lead_id,
  });
  return response.data;
};


export const createMessageDraft = async (
  linkedin_url: string,
  message_type: string = "first_message",
  lead_id: string = ""
): Promise<{ action: LinkedInAction; generated: Record<string, unknown> }> => {
  const response = await api.post("/linkedin/outreach/message", {
    linkedin_url,
    message_type,
    lead_id,
  });
  return response.data;
};

export const createFollowupDraft = async (data: {
  linkedin_url: string;
  lead_id?: string;
  lead_name?: string;
  lead_company?: string;
  lead_role?: string;
  sequence_number?: number;
}): Promise<{ action_id: string; draft_message: string; recommended_delay_hours: number; approach_used: string }> => {
  const response = await api.post("/linkedin/outreach/followup", data);
  return response.data;
};

// ── Approval ──────────────────────────────────────────────────────────────

export const getPendingActions = async (): Promise<{ actions: LinkedInAction[]; count: number }> => {
  const response = await api.get<{ status: string; actions: LinkedInAction[]; count: number }>(
    "/linkedin/outreach/pending"
  );
  return response.data;
};

export const approveAction = async (
  action_id: string
): Promise<{ action_status: string; result: Record<string, unknown> }> => {
  const response = await api.post(`/linkedin/outreach/approve/${action_id}`);
  return response.data;
};

export const rejectAction = async (action_id: string): Promise<void> => {
  await api.post(`/linkedin/outreach/reject/${action_id}`);
};

export const editAction = async (action_id: string, message: string): Promise<void> => {
  await api.put(`/linkedin/outreach/edit/${action_id}`, { message });
};

export const rescheduleAction = async (action_id: string, execute_at: string): Promise<void> => {
  await api.post(`/linkedin/outreach/reschedule/${action_id}`, { execute_at });
};


// ── Campaigns ─────────────────────────────────────────────────────────────

export const createLinkedInCampaign = async (data: {
  name: string;
  description?: string;
  goal?: string;
  target_audience?: string;
  daily_connection_limit?: number;
  daily_message_limit?: number;
}): Promise<LinkedInCampaign> => {
  const response = await api.post<{ status: string; campaign: LinkedInCampaign }>(
    "/linkedin/campaigns",
    data
  );
  return response.data.campaign;
};

export const getLinkedInCampaigns = async (): Promise<LinkedInCampaign[]> => {
  const response = await api.get<{ status: string; campaigns: LinkedInCampaign[] }>(
    "/linkedin/campaigns"
  );
  return response.data.campaigns || [];
};

export const startLinkedInCampaign = async (
  campaign_id: string
): Promise<{ total_actions: number; estimated_days: number }> => {
  const response = await api.post(`/linkedin/campaigns/${campaign_id}/start`);
  return response.data;
};

export const pauseLinkedInCampaign = async (campaign_id: string): Promise<void> => {
  await api.post(`/linkedin/campaigns/${campaign_id}/pause`);
};

// ── Conversations ─────────────────────────────────────────────────────────

export const getLinkedInConversations = async (): Promise<LinkedInConversation[]> => {
  const response = await api.get<{ status: string; conversations: LinkedInConversation[] }>(
    "/linkedin/conversations"
  );
  return response.data.conversations || [];
};

export const getLinkedInConversation = async (
  contact_id: string
): Promise<LinkedInConversation | null> => {
  const response = await api.get<{ status: string; conversation: LinkedInConversation }>(
    `/linkedin/conversations/${contact_id}`
  );
  return response.data.conversation || null;
};

// ── Analytics ─────────────────────────────────────────────────────────────

export const getLinkedInAnalytics = async (): Promise<LinkedInAnalytics> => {
  const response = await api.get<{ status: string } & LinkedInAnalytics>("/linkedin/analytics");
  return response.data;
};

// ── Relationships ─────────────────────────────────────────────────────────

export const getLinkedInRelationships = async (): Promise<LinkedInRelationship[]> => {
  const response = await api.get<{ status: string; relationships: LinkedInRelationship[] }>(
    "/linkedin/relationships"
  );
  return response.data.relationships || [];
};

// ── History ───────────────────────────────────────────────────────────────

export const getLinkedInHistory = async (
  page: number = 1,
  page_size: number = 20,
  status?: string
): Promise<{ actions: LinkedInAction[]; total: number; page: number; total_pages: number }> => {
  const params: Record<string, string | number> = { page, page_size };
  if (status) params.status = status;
  const response = await api.get("/linkedin/history", { params });
  return response.data;
};

// ── Queue Status ──────────────────────────────────────────────────────────

export const getLinkedInQueueStatus = async (): Promise<LinkedInQueueStatus> => {
  const response = await api.get<{ status: string } & LinkedInQueueStatus>("/linkedin/queue");
  return response.data;
};

// ── Settings LLM Toggle ───────────────────────────────────────────────────

export const getLLMStatus = async (section: string = "linkedin"): Promise<{ disabled: boolean }> => {
  const response = await api.get<{ disabled: boolean }>(`/linkedin/settings/llm?section=${section}`);
  return response.data;
};

export const toggleLLMStatus = async (disabled: boolean, section: string = "linkedin"): Promise<{ disabled: boolean }> => {
  const response = await api.post<{ disabled: boolean }>("/linkedin/settings/llm", { disabled, section });
  return response.data;
};

// ── Settings Auto-Reply Toggle ───────────────────────────────────────────

export const getAutoReplyStatus = async (): Promise<{ enabled: boolean }> => {
  const response = await api.get<{ enabled: boolean }>("/linkedin/settings/auto-reply");
  return response.data;
};

export const toggleAutoReplyStatus = async (enabled: boolean): Promise<{ enabled: boolean }> => {
  const response = await api.post<{ enabled: boolean }>("/linkedin/settings/auto-reply", { enabled });
  return response.data;
};

