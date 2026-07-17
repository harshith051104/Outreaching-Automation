import api from "./api";

export const getLLMStatus = async (section: string): Promise<{ disabled: boolean }> => {
  const response = await api.get<{ disabled: boolean }>(`/system/llm-status`, {
    params: { section },
  });
  return response.data;
};

export const toggleLLMStatus = async (disabled: boolean, section: string): Promise<{ success: boolean }> => {
  const response = await api.post<{ success: boolean }>(`/system/llm-toggle`, {
    disabled,
    section,
  });
  return response.data;
};
