"""
Pitch Deck Generation Service.

Synthesizes startup parameters (name, problem, solution, market, ask) into
a structured 10-slide outline schema for PptxGenJS client-side rendering.
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.config.llm_router import UnifiedLLMRouter
from app.models.pitch_deck import PitchDeck

logger = logging.getLogger(__name__)


class PitchDeckService:
    """Orchestrates generation and retrieval of AI pitch decks."""

    @staticmethod
    async def generate_deck(
        user_id: str,
        campaign_id: str,
        startup_name: str,
        problem: str,
        solution: str,
        market: str,
        traction: str,
        competitors: str,
        funding_ask: str
    ) -> Dict[str, Any]:
        """
        Calls Groq to generate slide titles, headers, bullet points,
        and design/layout hints for the 10 slides, then stores them in MongoDB.
        """
        slides = await PitchDeckService._synthesize_slides_with_llm(
            startup_name, problem, solution, market, traction, competitors, funding_ask
        )

        db = await get_database()
        
        deck_model = PitchDeck(
            user_id=user_id,
            campaign_id=campaign_id,
            startup_name=startup_name,
            problem=problem,
            solution=solution,
            market_size=market,
            traction=traction,
            competitors=competitors,
            funding_ask=funding_ask,
            slides=slides
        )

        deck_data = deck_model.to_dict()
        await db.pitch_decks.insert_one(deck_data)
        deck_data["id"] = deck_data.pop("_id")

        return deck_data

    @staticmethod
    async def _synthesize_slides_with_llm(
        name: str, problem: str, solution: str, market: str,
        traction: str, competitors: str, ask: str
    ) -> List[Dict[str, Any]]:
        """Call Groq to draft professional copy, layout tips, and text for the 10 slides."""
        from groq import Groq
        from app.config.settings import settings

        system_prompt = (
            "You are an elite Pitch Deck designer, business strategist, and VC pitch coach.\n"
            "Your job is to generate a comprehensive, highly-structured 10-slide outline for a pitch deck.\n"
            "For each slide, specify the title, subtitle, bullets (3-4 text points), slide_type, layout_hint, "
            "and additional structured data depending on the slide's role (e.g., key_stats, competitor_matrix, "
            "pricing_plans, team_members, use_of_funds) so the compiler can render premium graphical slides."
        )

        user_prompt = f"""
        Startup Name: {name}
        Problem Statement: {problem}
        Solution: {solution}
        Market Size/ICP: {market}
        Traction: {traction}
        Competitors: {competitors}
        Funding Ask: {ask}

        Return exactly 10 slides in order:
        1. Cover (Title, Subtitle, Startup Name) -> slide_type: "cover", layout_hint: "hero"
        2. Problem (Core pain point) -> slide_type: "problem", layout_hint: "split"
        3. Solution (Value prop, how it works) -> slide_type: "solution", layout_hint: "cards"
        4. Market (TAM, SAM, SOM) -> slide_type: "market", layout_hint: "dashboard", include "key_stats" (label, value)
        5. Product (Core features, visual mockup hint) -> slide_type: "product", layout_hint: "mockup"
        6. Business Model (Monetization & tiers) -> slide_type: "business_model", layout_hint: "cards", include "pricing_plans" (name, price, features)
        7. Traction (Metrics, growth rates) -> slide_type: "traction", layout_hint: "dashboard", include "key_stats" (label, value)
        8. Competitors (Competitive matrix table) -> slide_type: "competitors", layout_hint: "table", include "competitor_matrix" (headers: list of strings, rows: list of lists of strings) comparing Us vs competitors
        9. Team (Key founders) -> slide_type: "team", layout_hint: "cards", include "team_members" (name, role, background)
        10. Ask (Funding requirement & allocation) -> slide_type: "ask", layout_hint: "split", include "use_of_funds" (area, pct)

        Provide ONLY a valid JSON object matching this schema:
        {{
            "slides": [
                {{
                    "slide_number": 1,
                    "slide_type": "cover",
                    "title": "Slide Title",
                    "subtitle": "Slide Subtitle",
                    "bullets": ["Bullet 1", "Bullet 2"],
                    "layout_hint": "hero",
                    "background_color": "#0B0F19",
                    "key_stats": [
                        {{"label": "TAM", "value": "$10B"}}
                    ],
                    "pricing_plans": [
                        {{"name": "Growth", "price": "$99/mo", "features": ["feature 1"]}}
                    ],
                    "competitor_matrix": {{
                        "headers": ["Feature", "Us", "Competitor A"],
                        "rows": [["Feature 1", "Yes", "No"]]
                    }},
                    "team_members": [
                        {{"name": "CEO Name", "role": "CEO & Founder", "background": "Ex-Google PM"}}
                    ],
                    "use_of_funds": [
                        {{"area": "Product Development", "pct": "40%"}}
                    ]
                }}
            ]
        }}
        """

        def _call_groq(model: str) -> str:
            client = Groq(api_key=settings.GROQ_API_KEY)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content or "{}"

        try:
            response_content = await UnifiedLLMRouter.run_with_fallback(
                role="Campaign Strategist",
                client_call_func=_call_groq
            )
            data = json.loads(response_content)
            return data.get("slides", [])
        except Exception as exc:
            logger.exception("Failed to generate slide JSON structure via LLM: %s", exc)
            return [{"slide_number": i, "title": f"Slide {i}", "bullets": ["AI generation failed"]} for i in range(1, 11)]