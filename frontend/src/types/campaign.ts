export interface CampaignSettings {
  max_emails_per_day: number;
  delay_between_emails_seconds: number;
  follow_up_count: number;
  follow_up_delay_hours: number;
  tone: string;
  timezone: string;
}

export interface SequenceStep {
  step_number: number;
  channel: string;
  delay_days: number;
  subject_template?: string;
  body_template?: string;
  notes?: string;
}

export interface Campaign {
  id: string;
  user_id: string;
  name: string;
  description: string;
  status: string;
  subject_template: string;
  body_template: string;
  gmail_account_id: string;
  settings: CampaignSettings;
  sequence_steps?: SequenceStep[];
  total_leads: number;
  emails_sent: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignCreate {
  name: string;
  description?: string;
  subject_template?: string;
  body_template?: string;
  gmail_account_id?: string;
  settings?: CampaignSettings;
  sequence_steps?: SequenceStep[];
}