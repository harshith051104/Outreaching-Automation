export interface GmailAccount {
  id: string;
  email: string;
  connected_at: string;
  is_active: boolean;
  name?: string;
}

export interface GmailMessage {
  id: string;
  thread_id: string;
  subject: string;
  from_email: string;
  snippet: string;
  date: string;
}
