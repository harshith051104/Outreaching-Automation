import api from "./api";

export interface GenerateDeckRequest {
  campaign_id?: string;
  startup_name: string;
  problem: string;
  solution: string;
  market: string;
  traction: string;
  competitors: string;
  funding_ask: string;
}

export interface PitchDeck {
  id?: string;
  user_id: string;
  campaign_id: string;
  startup_name: string;
  problem?: string;
  solution?: string;
  market_size?: string;
  traction?: string;
  competitors?: string;
  funding_ask?: string;
  slides: Array<{
    slide_number: number;
    title: string;
    bullets: string[];
    visual_layout_hint?: string;
  }>;
  created_at: string;
  updated_at?: string;
}

export const generatePitchDeck = async (data: GenerateDeckRequest): Promise<PitchDeck> => {
  const response = await api.post<{ status: string; pitch_deck: PitchDeck }>("/pitch-decks/generate", data);
  return response.data.pitch_deck;
};

export const getPitchDecks = async (): Promise<PitchDeck[]> => {
  const response = await api.get<{ status: string; pitch_decks: PitchDeck[] }>("/pitch-decks/my-decks");
  return response.data.pitch_decks || [];
};
