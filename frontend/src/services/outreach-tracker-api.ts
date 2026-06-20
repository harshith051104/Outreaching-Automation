/**
 * Outreach Tracker API Service
 *
 * Manages the lead tracking board with 13 outreach milestone checkboxes,
 * timeline events, and team progress aggregation.
 */

import api from "./api";

export interface TrackerLead {
  id: string;
  name: string;
  email: string;
  company: string;
  linkedin: string;
  role: string;
  campaign_id: string;
  user_id: string;
  status: string;
  focus: string;
  assigned_user: string;
  notes: string;

  // 13 tracking checkboxes
  linkedin_followed: boolean;
  linkedin_connection_sent: boolean;
  linkedin_connection_accepted: boolean;
  linkedin_first_message_sent: boolean;
  linkedin_reply_received: boolean;
  email_sent: boolean;
  email_opened: boolean;
  email_replied: boolean;
  followup_1_sent: boolean;
  followup_2_sent: boolean;
  followup_3_sent: boolean;
  meeting_scheduled: boolean;
  opportunity_closed: boolean;

  last_activity_at: string | null;
  next_followup_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimelineEvent {
  id: string;
  lead_id: string;
  user_id: string;
  campaign_id: string;
  event_type: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface TeamProgress {
  assigned_user: string;
  total: number;
  linkedin_connection_sent: number;
  linkedin_connection_accepted: number;
  linkedin_first_message_sent: number;
  linkedin_reply_received: number;
  email_sent: number;
  email_opened: number;
  email_replied: number;
  followup_1_sent: number;
  followup_2_sent: number;
  followup_3_sent: number;
  meeting_scheduled: number;
  opportunity_closed: number;
}

export interface TrackerFilters {
  campaign_id?: string;
  assigned_user?: string;
  status?: string;
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: 1 | -1;
}

export interface TrackerResponse {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  leads: TrackerLead[];
}

// Human-readable labels for checkbox fields
export const CHECKBOX_LABELS: Record<string, string> = {
  linkedin_followed: "LinkedIn Followed",
  linkedin_connection_sent: "Connection Sent",
  linkedin_connection_accepted: "Connection Accepted",
  linkedin_first_message_sent: "First Message Sent",
  linkedin_reply_received: "LinkedIn Reply",
  email_sent: "Email Sent",
  email_opened: "Email Opened",
  email_replied: "Email Replied",
  followup_1_sent: "Follow-up #1",
  followup_2_sent: "Follow-up #2",
  followup_3_sent: "Follow-up #3",
  meeting_scheduled: "Meeting Scheduled",
  opportunity_closed: "Deal Closed",
};

export const CHECKBOX_FIELDS = Object.keys(CHECKBOX_LABELS);

export const CHECKBOX_ICONS: Record<string, string> = {
  linkedin_followed: "👋",
  linkedin_connection_sent: "📤",
  linkedin_connection_accepted: "🤝",
  linkedin_first_message_sent: "💬",
  linkedin_reply_received: "💭",
  email_sent: "📧",
  email_opened: "👁",
  email_replied: "↩️",
  followup_1_sent: "📨",
  followup_2_sent: "📩",
  followup_3_sent: "📬",
  meeting_scheduled: "📅",
  opportunity_closed: "✅",
};

/**
 * Get paginated, filtered leads for the tracker board.
 */
export async function getTrackerLeads(filters: TrackerFilters = {}): Promise<TrackerResponse> {
  const params: Record<string, string | number> = {};
  if (filters.campaign_id) params.campaign_id = filters.campaign_id;
  if (filters.assigned_user) params.assigned_user = filters.assigned_user;
  if (filters.status) params.status = filters.status;
  if (filters.search) params.search = filters.search;
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;
  if (filters.sort_by) params.sort_by = filters.sort_by;
  if (filters.sort_dir !== undefined) params.sort_dir = filters.sort_dir;

  const res = await api.get("/outreach-tracker", { params });
  return res.data;
}

/**
 * Update one or more tracking fields for a lead.
 */
export async function updateCheckboxes(
  leadId: string,
  updates: Record<string, boolean | string>
): Promise<TrackerLead> {
  const res = await api.patch(`/outreach-tracker/${leadId}/checkboxes`, { updates });
  return res.data;
}

/**
 * Get the activity timeline for a lead (newest first).
 */
export async function getTimeline(leadId: string, limit = 100): Promise<TimelineEvent[]> {
  const res = await api.get(`/outreach-tracker/${leadId}/timeline`, { params: { limit } });
  return res.data;
}

/**
 * Log a manual timeline event for a lead.
 */
export async function logTimelineEvent(
  leadId: string,
  event_type: string,
  description: string,
  metadata: Record<string, unknown> = {}
): Promise<TimelineEvent> {
  const res = await api.post(`/outreach-tracker/${leadId}/timeline`, {
    event_type,
    description,
    metadata,
  });
  return res.data;
}

/**
 * Get team progress stats per assigned user (manager/admin only).
 */
export async function getTeamProgress(campaignId?: string): Promise<TeamProgress[]> {
  const params: Record<string, string> = {};
  if (campaignId) params.campaign_id = campaignId;
  const res = await api.get("/outreach-tracker/team-progress", { params });
  return res.data;
}

export interface TrackerUser {
  id: string;
  name: string;
  display_name: string;
  email: string;
  role?: string;
}

export async function getTrackerUsers(): Promise<TrackerUser[]> {
  const res = await api.get("/outreach-tracker/users");
  return res.data;
}

export async function createTrackerUser(data: {
  name: string;
  display_name?: string;
  email: string;
  password?: string;
  role?: string;
}): Promise<TrackerUser> {
  const res = await api.post("/outreach-tracker/users", data);
  return res.data;
}

export async function updateTrackerUser(
  userId: string,
  updates: {
    name?: string;
    display_name?: string;
    email?: string;
    role?: string;
  }
): Promise<TrackerUser> {
  const res = await api.patch(`/outreach-tracker/users/${userId}`, updates);
  return res.data;
}

export async function deleteTrackerUser(userId: string): Promise<{ message: string }> {
  const res = await api.delete(`/outreach-tracker/users/${userId}`);
  return res.data;
}


export async function triggerPullSync(): Promise<{ message: string }> {
  const res = await api.post("/outreach-tracker/sync/pull");
  return res.data;
}

export async function triggerPushSync(campaignId?: string): Promise<{ message: string }> {
  const res = await api.post("/outreach-tracker/sync/push", null, {
    params: campaignId ? { campaign_id: campaignId } : {},
  });
  return res.data;
}


