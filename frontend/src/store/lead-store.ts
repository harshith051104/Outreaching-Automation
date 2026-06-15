import { create } from "zustand";
import type { Lead } from "@/types/lead";

interface LeadState {
  leads: Lead[];
  selectedLead: Lead | null;
  loading: boolean;
  setLeads: (leads: Lead[]) => void;
  setSelectedLead: (lead: Lead | null) => void;
  addLead: (lead: Lead) => void;
  updateLead: (id: string, lead: Partial<Lead>) => void;
  setLoading: (loading: boolean) => void;
}

export const useLeadStore = create<LeadState>((set) => ({
  leads: [],
  selectedLead: null,
  loading: false,

  setLeads: (leads) => set({ leads }),

  setSelectedLead: (lead) => set({ selectedLead: lead }),

  addLead: (lead) =>
    set((state) => ({ leads: [...state.leads, lead] })),

  updateLead: (id, updatedFields) =>
    set((state) => ({
      leads: state.leads.map((l) =>
        l.id === id ? { ...l, ...updatedFields } : l
      ),
      selectedLead:
        state.selectedLead?.id === id
          ? { ...state.selectedLead, ...updatedFields }
          : state.selectedLead,
    })),

  setLoading: (loading) => set({ loading }),
}));
