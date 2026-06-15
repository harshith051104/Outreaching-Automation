export interface DashboardStats {
  total_campaigns: number;
  active_campaigns: number;
  total_leads: number;
  total_emails_sent: number;
  total_opens: number;
  total_clicks: number;
  total_replies: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
}

export interface CampaignAnalytics {
  campaign_id: string;
  emails_sent: number;
  emails_failed: number;
  total_opens: number;
  unique_opens: number;
  total_clicks: number;
  unique_clicks: number;
  total_replies: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
}

export interface DailyStats {
  date: string;
  opens: number;
  clicks: number;
  replies: number;
  emails_sent: number;
}