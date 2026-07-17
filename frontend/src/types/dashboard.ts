export type EventType =
  | "campaign.started"
  | "campaign.paused"
  | "campaign.resumed"
  | "campaign.completed"
  | "campaign.failed"
  | "campaign.progress"
  | "email.sent"
  | "email.failed"
  | "email.delivered"
  | "email.opened"
  | "email.clicked"
  | "reply.received"
  | "reply.classified"
  | "lead.updated"
  | "lead.processed"
  | "ai.started"
  | "ai.progress"
  | "ai.completed"
  | "ai.failed"
  | "system.health"
  | "worker.status"
  | "notification.created"
  | "dashboard.refresh"
  | "custom";

export interface WSEvent {
  event_type: EventType;
  data: Record<string, unknown>;
  event_id: string;
  timestamp: string;
  campaign_id?: string;
}

export type NotificationSeverity = "info" | "warning" | "error" | "success";

export interface DashboardNotification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  severity: NotificationSeverity;
  reference_id: string;
  reference_type: string;
  is_read: boolean;
  created_at: string;
}

export interface ActivityItem {
  id: string;
  user_id: string;
  user_name: string;
  action: string;
  reference_id: string;
  reference_type: string;
  details: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export type HealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  latency_ms: number;
  message: string;
  last_checked: string;
}

export interface SystemHealth {
  status: HealthStatus;
  components: ComponentHealth[];
  uptime_seconds: number;
  checked_at: string;
}

export interface CampaignSummary {
  campaign_id: string;
  name: string;
  status: string;
  total_leads: number;
  emails_sent: number;
  emails_opened: number;
  emails_clicked: number;
  emails_replied: number;
  emails_failed: number;
  progress_pct: number;
  health_score: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  total_campaigns: number;
  active_campaigns: number;
  total_leads: number;
  emails_sent_today: number;
  emails_sent_total: number;
  replies_received: number;
  meetings_scheduled: number;
  pending_tasks: number;
  active_users: number;
  recent_activity: ActivityItem[];
  campaigns: CampaignSummary[];
}

export interface ExecutionLog {
  execution_id: string;
  campaign_id: string;
  lead_id: string;
  module: string;
  status: string;
  message: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface DashboardMetrics {
  ws_connections: number;
  ws_messages_sent: number;
  ws_messages_failed: number;
  api_requests: number;
  api_errors: number;
  events_routed: number;
  notifications_pushed: number;
  avg_api_latency_ms: number;
  avg_ws_latency_ms: number;
}

export interface LeadStats {
  total: number;
  new: number;
  contacted: number;
  replied: number;
  meeting: number;
  qualified: number;
}

export interface EmailStats {
  total_sent: number;
  total_delivered: number;
  total_opened: number;
  total_clicked: number;
  total_replied: number;
  total_failed: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
}
