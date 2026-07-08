export interface Lead {
  id: string;
  user_id: string;
  campaign_id: string;
  name: string;
  first_name?: string;
  last_name?: string;
  email: string;
  company: string;
  website: string;
  role: string;
  focus?: string;
  status: string;
  score: number;
  custom_fields?: Record<string, any>;
  research_data: Record<string, unknown>;
  personalization_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LeadCreate {
  campaign_id: string;
  name: string;
  email: string;
  company?: string;
  website?: string;
  role?: string;
  focus?: string;
  custom_fields?: Record<string, any>;
}