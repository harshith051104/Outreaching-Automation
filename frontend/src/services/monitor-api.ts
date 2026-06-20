import api from "./api";

// ── Reply Monitor ──────────────────────────────────────────────────────────

export interface Reply {
  id: string;
  email_id: string;
  campaign_id: string;
  lead_id: string;
  gmail_message_id: string;
  from_email: string;
  subject: string;
  snippet: string;
  body: string;
  classification: string | null;
  sentiment: string | null;
  received_at: string;
  gmail_account_id?: string;
  draft_response?: {
    subject: string;
    body_text: string;
    body_html: string;
    generated_at: string;
    status: "pending" | "approved" | "rejected" | "sent" | "failed";
    classification?: {
      classification: string;
      sentiment: string;
      confidence_score: number;
      lead_score_delta: number;
      reasoning: string;
      recommended_action: string;
    };
  };
  lead?: {
    id: string;
    name: string;
    email: string;
    company: string;
    role: string;
  };
  campaign?: {
    id: string;
    name: string;
    gmail_account_id?: string;
  };
}

export interface MonitorStats {
  total_replies: number;
  pending_drafts: number;
  sent_responses: number;
  classification_breakdown: Record<string, number>;
}

export async function getPendingReplies(): Promise<Reply[]> {
  const response = await api.get("/reply-monitor/replies");
  return response.data;
}

export async function getReplyDetails(replyId: string): Promise<Reply> {
  const response = await api.get(`/reply-monitor/replies/${replyId}`);
  return response.data;
}

export async function generateDraft(
  replyId: string,
  gmailAccountId?: string
): Promise<{ reply_id: string; draft: Reply["draft_response"]; classification: unknown }> {
  const url = `/reply-monitor/replies/${replyId}/generate-draft${gmailAccountId ? `?gmail_account_id=${gmailAccountId}` : ""}`;
  const response = await api.post(url);
  return response.data;
}

export async function approveDraft(
  replyId: string
): Promise<{ status: string; reply_id: string; gmail_message_id: string }> {
  const response = await api.post(`/reply-monitor/replies/${replyId}/approve`);
  return response.data;
}

export async function rejectDraft(
  replyId: string,
  reason?: string
): Promise<{ status: string; reply_id: string }> {
  const response = await api.post(`/reply-monitor/replies/${replyId}/reject`, { reason });
  return response.data;
}

export async function deleteReply(
  replyId: string
): Promise<{ status: string; message: string }> {
  const response = await api.delete(`/reply-monitor/replies/${replyId}`);
  return response.data;
}

export async function updateDraft(
  replyId: string,
  subject: string,
  body_text: string,
  gmailAccountId?: string
): Promise<{ status: string; reply_id: string }> {
  const response = await api.patch(`/reply-monitor/replies/${replyId}/draft`, { 
    subject, 
    body_text, 
    gmail_account_id: gmailAccountId 
  });
  return response.data;
}

export async function getMonitorStats(): Promise<MonitorStats> {
  const response = await api.get("/reply-monitor/stats");
  return response.data;
}

// ── Webhooks ───────────────────────────────────────────────────────────────

export interface Webhook {
  id: string;
  user_id: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

export interface WebhookEventType {
  event_type: string;
  category: string;
  description: string;
}

export async function getWebhooks(): Promise<Webhook[]> {
  const response = await api.get("/webhooks");
  return response.data;
}

export async function createWebhook(
  url: string,
  events: string[],
  secret?: string
): Promise<Webhook> {
  const response = await api.post("/webhooks", { url, events, secret });
  return response.data;
}

export async function deleteWebhook(webhookId: string): Promise<void> {
  await api.delete(`/webhooks/${webhookId}`);
}

export async function getWebhookEventTypes(): Promise<WebhookEventType[]> {
  const response = await api.get("/webhooks/event-types");
  return response.data;
}

// ── Lead Lists & Labels ────────────────────────────────────────────────────

export interface LeadList {
  id: string;
  name: string;
  description: string;
  total_leads: number;
  created_at: string;
}

export interface LeadLabel {
  id: string;
  name: string;
  color: string;
  description: string;
  created_at: string;
}

export async function getLeadLists(): Promise<LeadList[]> {
  const response = await api.get("/leads/lists");
  return response.data;
}

export async function createLeadList(
  name: string,
  description?: string
): Promise<LeadList> {
  const response = await api.post("/leads/lists", { name, description });
  return response.data;
}

export async function getLeadLabels(): Promise<LeadLabel[]> {
  const response = await api.get("/leads/labels");
  return response.data;
}

export async function createLeadLabel(
  name: string,
  color?: string,
  description?: string
): Promise<LeadLabel> {
  const response = await api.post("/leads/labels", { name, color, description });
  return response.data;
}

// ── Chat Sessions ──────────────────────────────────────────────────────────

export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  llm_provider?: string;
  llm_model?: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  actions_taken?: { tool: string; arguments: Record<string, unknown> }[];
  created_at: string;
}

export async function getChatSessions(): Promise<ChatSession[]> {
  const response = await api.get("/chatbot/sessions");
  return response.data;
}

export async function createChatSession(
  title?: string
): Promise<ChatSession> {
  const response = await api.post("/chatbot/sessions", { title: title || "New Chat" });
  return response.data;
}

export async function getChatSessionMessages(
  sessionId: string
): Promise<ChatMessage[]> {
  const response = await api.get(`/chatbot/sessions/${sessionId}/messages`);
  return response.data;
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await api.delete(`/chatbot/sessions/${sessionId}`);
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  uploadedFiles?: { name: string; url: string; type: string; id: string }[],
  llmProvider?: string,
  llmModel?: string
): Promise<{ response: string; actions_taken: { tool: string; arguments: Record<string, unknown> }[]; pending_approval?: any }> {
  const payload: any = {
    message,
    uploaded_files: uploadedFiles?.map(f => ({ name: f.name, url: f.url })) || [],
  };
  if (llmProvider) payload.llm_provider = llmProvider;
  if (llmModel) payload.llm_model = llmModel;
  const response = await api.post(`/chatbot/sessions/${sessionId}/chat`, payload);
  return response.data;
}
