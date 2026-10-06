import api from "./api";
import type { UserMin } from "./task-api";

export interface Suggestion {
  id: string;
  user_id: string | null;
  author_info?: UserMin | null;
  title: string;
  description: string;
  category: "suggestion" | "feature_request" | "improvement" | "feedback" | "bug_report";
  anonymous: boolean;
  status: "pending" | "under_review" | "accepted" | "rejected" | "implemented";
  votes: string[];
  created_at: string;
  updated_at: string;

  // Widget specific context fields
  submitted_from: string;
  page_name?: string | null;
  page_url?: string | null;
  screenshot_url?: string | null;
  has_screenshot: boolean;
  browser_info?: string | null;

  // AI enhanced fields
  ai_summary?: string | null;
  ai_priority?: string | null;
  ai_business_impact?: string | null;
  ai_suggested_category?: string | null;
}

export interface SuggestionComment {
  id: string;
  suggestion_id: string;
  user_id: string;
  author_info?: UserMin;
  message: string;
  created_at: string;
}

export const getSuggestions = async (params?: {
  category?: string;
  status?: string;
  submitted_from?: string;
  has_screenshot?: boolean;
  anonymous?: boolean;
}): Promise<Suggestion[]> => {
  const response = await api.get<Suggestion[]>("/suggestions", { params });
  return response.data;
};

export const getSuggestion = async (id: string): Promise<Suggestion> => {
  const response = await api.get<Suggestion>(`/suggestions/${id}`);
  return response.data;
};

export const createSuggestion = async (data: {
  title: string;
  description: string;
  category: string;
  anonymous: boolean;
  submitted_from?: string;
  page_name?: string;
  page_url?: string;
  screenshot_url?: string;
  has_screenshot?: boolean;
  browser_info?: string;
}): Promise<Suggestion> => {
  const response = await api.post<Suggestion>("/suggestions", data);
  return response.data;
};

export const updateSuggestionStatus = async (
  id: string,
  status: string
): Promise<Suggestion> => {
  const response = await api.patch<Suggestion>(`/suggestions/${id}/status`, { status });
  return response.data;
};

export const upvoteSuggestion = async (id: string): Promise<Suggestion> => {
  const response = await api.post<Suggestion>(`/suggestions/${id}/vote`);
  return response.data;
};

export const getSuggestionComments = async (
  suggestionId: string
): Promise<SuggestionComment[]> => {
  const response = await api.get<SuggestionComment[]>(`/suggestions/${suggestionId}/comments`);
  return response.data;
};

export const addSuggestionComment = async (
  suggestionId: string,
  message: string
): Promise<SuggestionComment> => {
  const response = await api.post<SuggestionComment>(`/suggestions/${suggestionId}/comments`, {
    message,
  });
  return response.data;
};

export const deleteSuggestion = async (id: string): Promise<void> => {
  await api.delete(`/suggestions/${id}`);
};
