import { useAuthStore } from "@/store/auth-store";

/**
 * Custom React hook to interact with the authentication store.
 */
export function useAuth() {
  const { user, token, isAuthenticated, login, logout, loadFromStorage } = useAuthStore();

  return {
    user,
    token,
    isAuthenticated,
    login,
    logout,
    loadFromStorage,
  };
}
