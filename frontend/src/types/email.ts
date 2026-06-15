export interface Email {
  id: string;
  campaign_id: string;
  lead_id: string;
  subject: string;
  body_html: string;
  tracking_id: string;
  status: string;
  sequence_number: number;
  sent_at: string | null;
  created_at: string;
}

export interface TrackingEvent {
  id: string;
  tracking_id: string;
  event_type: string;
  ip_address: string;
  user_agent: string;
  url: string;
  timestamp: string;
}

export interface Reply {
  id: string;
  email_id: string;
  lead_id: string;
  body_text: string;
  classification: string;
  sentiment: string;
  confidence_score: number;
  received_at: string;
}
