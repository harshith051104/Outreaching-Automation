import api from "./api";

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatResponse {
  response: string;
  actions_taken: Array<{
    tool: string;
    arguments: Record<string, any>;
  }>;
}

export const sendChatbotMessage = async (
  message: string,
  history: ChatMessage[] = []
): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>("/chatbot/chat", {
    message,
    conversation_history: history.map(h => ({
      role: h.role,
      content: h.content
    })),
  });
  return response.data;
};
