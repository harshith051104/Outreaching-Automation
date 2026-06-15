import api from "./api";
import type { GmailAccount, GmailMessage } from "@/types/gmail";

export const getGmailAccounts = async (): Promise<GmailAccount[]> => {
  const response = await api.get<GmailAccount[]>("/gmail/accounts");
  return response.data;
};

export const disconnectGmailAccount = async (id: string): Promise<void> => {
  await api.delete(`/gmail/accounts/${id}`);
};

export const updateGmailAccountName = async (id: string, name: string): Promise<void> => {
  await api.put(`/gmail/accounts/${id}`, { name });
};

export const getGmailInbox = async (accountId: string): Promise<GmailMessage[]> => {
  const response = await api.get<GmailMessage[]>(`/gmail/inbox/${accountId}`);
  return response.data;
};

export const getGmailAuthUrl = async (): Promise<{ authorization_url: string; state: string }> => {
  const response = await api.get<{ authorization_url: string; state: string }>("/gmail/auth");
  return response.data;
};