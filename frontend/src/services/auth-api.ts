import api from "./api";
import type { User, LoginRequest, RegisterRequest, TokenResponse } from "@/types/auth";

export const register = async (data: RegisterRequest): Promise<User> => {
  const response = await api.post<User>("/auth/register", data);
  return response.data;
};

export const login = async (data: LoginRequest): Promise<TokenResponse & { user: User }> => {
  // Login returns token, but we also need to fetch user data
  const response = await api.post<TokenResponse>("/auth/login", {
    email: data.email,
    password: data.password,
  });
  // Store token in localStorage so the axios interceptor can use it for the next call
  if (typeof window !== "undefined") {
    localStorage.setItem("access_token", response.data.access_token);
  }
  // After login, fetch user profile (now the token is available in the header)
  const userResponse = await api.get<User>("/auth/me");
  return {
    ...response.data,
    user: userResponse.data,
  };
};

export const getMe = async (): Promise<User> => {
  const response = await api.get<User>("/auth/me");
  return response.data;
};

export const authApi = {
  register,
  login,
  getMe,
};