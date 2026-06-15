import api from "./api";

export interface GenerateCalendarRequest {
  campaign_id?: string;
  campaign_goal: string;
  target_audience: string;
  industry: string;
}

export interface LinkedInCalendar {
  id?: string;
  user_id: string;
  campaign_id: string;
  campaign_goal: string;
  target_audience: string;
  industry: string;
  pillars: string[];
  schedule: Array<{
    day: number;
    pillar: string;
    topic: string;
    hook_concept: string;
    generated_post: string;
    hashtags: string[];
  }>;
  created_at: string;
}

export const generateLinkedInCalendar = async (
  data: GenerateCalendarRequest
): Promise<LinkedInCalendar> => {
  const response = await api.post<{ status: string; content_calendar: LinkedInCalendar }>(
    "/linkedin/generate-calendar",
    data
  );
  return response.data.content_calendar;
};

export const getLinkedInCalendars = async (): Promise<LinkedInCalendar[]> => {
  const response = await api.get<{ status: string; calendars: LinkedInCalendar[] }>("/linkedin/calendars");
  return response.data.calendars || [];
};

// ── CSV Import Types ─────────────────────────────────────────────────────────

export interface CSVImportResult {
  status: string;
  filename: string;
  total_rows: number;
  valid_leads: number;
  leads_created: number;
  leads_updated: number;
  errors: string[];
}

export interface ParsedCSVPreview {
  total_rows: number;
  valid_leads: number;
  leads: LinkedInLeadPreview[];
  errors: string[];
}

export interface LinkedInLeadPreview {
  id: string;
  name?: string;
  email?: string;
  company?: string;
  role?: string;
  linkedin_url?: string;
  website?: string;
}

export interface LinkedInLead {
  id: string;
  user_id: string;
  campaign_id?: string;
  name: string;
  email?: string;
  company?: string;
  website?: string;
  role?: string;
  linkedin?: string;
  linkedin_url?: string;
  status: string;
  score: number;
  lead_quality_score: number;
  discovery_source: string;
  created_at: string;
  updated_at: string;
}

export interface BulkActionResult {
  requested: number;
  created: number;
  errors: string[];
}

// ── CSV Import API ────────────────────────────────────────────────────────────

export const importLeadsFromCSV = async (
  file: File,
  campaignId?: string
): Promise<CSVImportResult> => {
  const formData = new FormData();
  formData.append("file", file);
  if (campaignId) {
    formData.append("campaign_id", campaignId);
  }

  const response = await api.post<CSVImportResult>(
    "/linkedin/import-csv",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return response.data;
};

export const parseCSVPreview = async (file: File): Promise<ParsedCSVPreview> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post<ParsedCSVPreview>(
    "/linkedin/import-csv/parse",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return response.data;
};

export const getLinkedInLeads = async (
  campaignId?: string,
  limit: number = 100
): Promise<{ leads: LinkedInLead[]; count: number }> => {
  const params = new URLSearchParams();
  if (campaignId) params.append("campaign_id", campaignId);
  params.append("limit", limit.toString());

  const response = await api.get<{ leads: LinkedInLead[]; count: number }>(
    `/linkedin/leads?${params.toString()}`
  );
  return response.data;
};

export const bulkConnectLeads = async (
  leadIds: string[],
  note?: string
): Promise<BulkActionResult> => {
  const response = await api.post<BulkActionResult>(
    "/linkedin/leads/bulk-connect",
    { lead_ids: leadIds, note }
  );
  return response.data;
};

export const bulkMessageLeads = async (
  leadIds: string[],
  message: string
): Promise<BulkActionResult> => {
  const response = await api.post<BulkActionResult>(
    "/linkedin/leads/bulk-message",
    { lead_ids: leadIds, message }
  );
  return response.data;
};
