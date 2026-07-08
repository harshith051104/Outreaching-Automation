import api from "./api";

export interface UserMin {
  id: string;
  name: string;
  email: string;
}

export interface Task {
  id: string;
  user_id: string;
  title: string;
  description: string;
  status: "todo" | "in_progress" | "review" | "completed" | "blocked";
  priority: "low" | "medium" | "high" | "critical";
  due_date: string | null;
  assigned_to: string | null;
  assignee_info?: UserMin;
  creator_info?: UserMin;
  created_at: string;
  updated_at: string;
}

export interface TaskComment {
  id: string;
  task_id: string;
  user_id: string;
  message: string;
  created_at: string;
  author_info?: UserMin;
}

export interface Notification {
  id: string;
  user_id: string;
  sender_id: string | null;
  sender_info?: UserMin;
  type: string;
  title: string;
  message: string;
  reference_id: string;
  reference_type: "task" | "suggestion" | "linkedin_reply";
  is_read: boolean;
  created_at: string;
}

export interface DashboardStats {
  total_tasks: number;
  pending_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  total_suggestions: number;
  recent_activity: {
    id: string;
    user_id: string;
    user_name: string;
    action: string;
    reference_id: string;
    reference_type: string;
    details: string;
    created_at: string;
  }[];
}

// ── Tasks ─────────────────────────────────────────────────────────────────

export const getTasks = async (params?: {
  status?: string;
  priority?: string;
  assigned_to?: string;
  search?: string;
}): Promise<Task[]> => {
  const response = await api.get<Task[]>("/tasks", { params });
  return response.data;
};

export const getTask = async (id: string): Promise<Task> => {
  const response = await api.get<Task>(`/tasks/${id}`);
  return response.data;
};

export const createTask = async (data: {
  title: string;
  description?: string;
  status?: string;
  priority?: string;
  due_date?: string | null;
  assigned_to?: string | null;
}): Promise<Task> => {
  const response = await api.post<Task>("/tasks", data);
  return response.data;
};

export const updateTask = async (
  id: string,
  data: Partial<{
    title: string;
    description: string;
    status: string;
    priority: string;
    due_date: string | null;
    assigned_to: string | null;
  }>
): Promise<Task> => {
  const response = await api.put<Task>(`/tasks/${id}`, data);
  return response.data;
};

export const deleteTask = async (id: string): Promise<void> => {
  await api.delete(`/tasks/${id}`);
};

export const exportTasksToSheets = async (params?: {
  status?: string;
  priority?: string;
  assigned_to?: string;
  search?: string;
}): Promise<{ success: boolean; spreadsheet_url: string; title: string }> => {
  const response = await api.post<{ success: boolean; spreadsheet_url: string; title: string }>(
    "/tasks/export/sheets",
    null,
    { params }
  );
  return response.data;
};

// ── Task Comments ─────────────────────────────────────────────────────────

export const getTaskComments = async (taskId: string): Promise<TaskComment[]> => {
  const response = await api.get<TaskComment[]>(`/task-comments/${taskId}`);
  return response.data;
};

export const addTaskComment = async (
  taskId: string,
  message: string
): Promise<TaskComment> => {
  const response = await api.post<TaskComment>(`/task-comments/${taskId}`, { message });
  return response.data;
};

// ── Users (Team Members) ───────────────────────────────────────────────────

export const getTeamMembers = async (): Promise<UserMin[]> => {
  const response = await api.get<UserMin[]>("/auth/users");
  return response.data;
};

// ── Notifications ─────────────────────────────────────────────────────────

export const getNotifications = async (unreadOnly = false): Promise<Notification[]> => {
  const response = await api.get<Notification[]>("/notifications", {
    params: { unreadOnly },
  });
  return response.data;
};

export const getUnreadNotificationsCount = async (): Promise<number> => {
  const response = await api.get<{ count: number }>("/notifications/unread-count");
  return response.data.count;
};

export const markNotificationRead = async (id: string): Promise<void> => {
  await api.patch(`/notifications/${id}/read`);
};

export const markAllNotificationsRead = async (): Promise<void> => {
  await api.post("/notifications/read-all");
};

export const clearAllNotifications = async (): Promise<void> => {
  await api.delete("/notifications");
};

// ── Dashboard Stats ───────────────────────────────────────────────────────

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await api.get<DashboardStats>("/dashboard/stats");
  return response.data;
};
