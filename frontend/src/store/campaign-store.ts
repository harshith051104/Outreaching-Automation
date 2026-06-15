import { create } from "zustand";
import type { Campaign } from "@/types/campaign";

interface CampaignState {
  campaigns: Campaign[];
  activeCampaign: Campaign | null;
  loading: boolean;
  setCampaigns: (campaigns: Campaign[]) => void;
  setActiveCampaign: (campaign: Campaign | null) => void;
  addCampaign: (campaign: Campaign) => void;
  updateCampaign: (id: string, campaign: Partial<Campaign>) => void;
  removeCampaign: (id: string) => void;
  setLoading: (loading: boolean) => void;
}

export const useCampaignStore = create<CampaignState>((set) => ({
  campaigns: [],
  activeCampaign: null,
  loading: false,

  setCampaigns: (campaigns) => set({ campaigns }),

  setActiveCampaign: (campaign) => set({ activeCampaign: campaign }),

  addCampaign: (campaign) =>
    set((state) => ({ campaigns: [...state.campaigns, campaign] })),

  updateCampaign: (id, updatedFields) =>
    set((state) => ({
      campaigns: state.campaigns.map((c) =>
        c.id === id ? { ...c, ...updatedFields } : c
      ),
      activeCampaign:
        state.activeCampaign?.id === id
          ? { ...state.activeCampaign, ...updatedFields }
          : state.activeCampaign,
    })),

  removeCampaign: (id) =>
    set((state) => ({
      campaigns: state.campaigns.filter((c) => c.id !== id),
      activeCampaign:
        state.activeCampaign?.id === id ? null : state.activeCampaign,
    })),

  setLoading: (loading) => set({ loading }),
}));
