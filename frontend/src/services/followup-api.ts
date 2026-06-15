import api from "./api";

export interface FollowupTask {
  id: string;
  email_id: string;
  campaign_id: string;
  lead_id: string;
  user_id: string;
  sequence_number: number;
  status: "pending" | "executed" | "failed" | "cancelled";
  scheduled_at: string;
  executed_at: string | null;
  result_email_id: string | null;
  created_at: string;
  updated_at: string;
}

export const getFollowups = async (params: {
  campaign_id?: string;
  lead_id?: string;
  status?: string;
} = {}): Promise<FollowupTask[]> => {
  const response = await api.get<FollowupTask[]>("/followups", { params });
  return response.data;
};

export const executeFollowup = async (id: string): Promise<FollowupTask> => {
  const response = await api.post<FollowupTask>(`/followups/${id}/execute`);
  return response.data;
};

export const cancelFollowup = async (id: string): Promise<FollowupTask> => {
  const response = await api.put<FollowupTask>(`/followups/${id}/cancel`);
  return response.data;
};
