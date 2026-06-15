import { create } from "zustand";
import type { DashboardStats, CampaignAnalytics } from "@/types/analytics";

interface AnalyticsState {
  dashboardStats: DashboardStats | null;
  campaignAnalytics: CampaignAnalytics | null;
  loading: boolean;
  setDashboardStats: (stats: DashboardStats) => void;
  setCampaignAnalytics: (analytics: CampaignAnalytics | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useAnalyticsStore = create<AnalyticsState>((set) => ({
  dashboardStats: null,
  campaignAnalytics: null,
  loading: false,

  setDashboardStats: (stats) => set({ dashboardStats: stats }),

  setCampaignAnalytics: (analytics) => set({ campaignAnalytics: analytics }),

  setLoading: (loading) => set({ loading }),
}));
