import api from "./api";
import type {
  DashboardSummary,
  SystemHealth,
  ActivityItem,
  DashboardNotification,
  ExecutionLog,
  DashboardMetrics,
  LeadStats,
  EmailStats,
} from "@/types/dashboard";

const BASE = "/dashboard";

export const getDashboardSummary = async (userId?: string): Promise<DashboardSummary> => {
  const params = userId ? { user_id: userId } : {};
  const response = await api.get<DashboardSummary>(`${BASE}/summary`, { params });
  return response.data;
};

export const getSystemHealth = async (): Promise<SystemHealth> => {
  const response = await api.get<SystemHealth>(`${BASE}/health`);
  return response.data;
};

export const getLeadStats = async (userId?: string): Promise<LeadStats> => {
  const params = userId ? { user_id: userId } : {};
  const response = await api.get<LeadStats>(`${BASE}/leads/stats`, { params });
  return response.data;
};

export const getEmailStats = async (userId?: string): Promise<EmailStats> => {
  const params = userId ? { user_id: userId } : {};
  const response = await api.get<EmailStats>(`${BASE}/emails/stats`, { params });
  return response.data;
};

export const getActivityFeed = async (
  userId?: string,
  limit = 50
): Promise<{ activity: ActivityItem[]; total: number }> => {
  const params: Record<string, unknown> = { limit };
  if (userId) params.user_id = userId;
  const response = await api.get<{ activity: ActivityItem[]; total: number }>(
    `${BASE}/activity`,
    { params }
  );
  return response.data;
};

export const getNotifications = async (
  userId?: string,
  unreadOnly = false,
  limit = 50
): Promise<{ notifications: DashboardNotification[]; unread_count: number }> => {
  const params: Record<string, unknown> = { unread_only: unreadOnly, limit };
  if (userId) params.user_id = userId;
  const response = await api.get<{ notifications: DashboardNotification[]; unread_count: number }>(
    `${BASE}/notifications`,
    { params }
  );
  return response.data;
};

export const getUnreadNotificationCount = async (userId?: string): Promise<number> => {
  const params = userId ? { user_id: userId } : {};
  const response = await api.get<{ unread_count: number }>(
    `${BASE}/notifications/unread-count`,
    { params }
  );
  return response.data.unread_count;
};

export const markNotificationRead = async (
  userId: string,
  notificationId: string
): Promise<boolean> => {
  const response = await api.patch<{ success: boolean }>(
    `${BASE}/notifications/${notificationId}/read`,
    null,
    { params: { user_id: userId } }
  );
  return response.data.success;
};

export const markAllNotificationsRead = async (userId: string): Promise<number> => {
  const response = await api.post<{ updated: number }>(
    `${BASE}/notifications/read-all`,
    null,
    { params: { user_id: userId } }
  );
  return response.data.updated;
};

export const getExecutionLogs = async (
  filters: { campaign_id?: string; lead_id?: string; module?: string } = {},
  limit = 50,
  offset = 0
): Promise<{ logs: ExecutionLog[]; total: number }> => {
  const response = await api.get<{ logs: ExecutionLog[]; total: number }>(
    `${BASE}/logs`,
    { params: { ...filters, limit, offset } }
  );
  return response.data;
};

export const getDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const response = await api.get<DashboardMetrics>(`${BASE}/metrics`);
  return response.data;
};
