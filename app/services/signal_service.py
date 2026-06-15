"""
Signal Intelligence and Scraper Service.

Leverages Tavily and Firecrawl to harvest signals (such as hiring activity,
pricing adjustments, tech stack updates, expansions) for target companies,
and parses them using the Signal Intelligence Agent schema.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.config.llm_router import UnifiedLLMRouter
from app.services.tavily_service import TavilyService
from app.services.firecrawl_service import FirecrawlService
from app.services.qdrant_service import store_document
from app.models.signal import Signal

logger = logging.getLogger(__name__)


class SignalService:
    """Gathers and analyses business expansion and job opening signals."""

    def __init__(self):
        self.tavily = TavilyService()
        self.firecrawl = FirecrawlService()

    async def gather_and_store_signals(
        self,
        lead_id: str,
        company_name: str,
        website_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Gathers news, expansions, job postings, and pricing indicators,
        parses them through the Signal Intelligence Agent, and writes results
        to MongoDB + Qdrant.
        """
        db = await get_database()
        raw_context = []

        search_query = f"{company_name} hiring jobs funding press release tech stack expansion"
        logger.info("Gathering Tavily signals for %s...", company_name)
        tavily_results = await self.tavily.search(query=search_query, max_results=4)
        for r in tavily_results:
            raw_context.append(f"Source: {r.get('url')}\nContent: {r.get('content')}")

        if website_url:
            logger.info("Scraping website '%s' with Firecrawl for main page insights...", website_url)
            scraped_content = await self.firecrawl.scrape_url(website_url)
            if scraped_content:
                raw_context.append(f"Main Website Content:\n{scraped_content[:4000]}")
                
            careers_url = f"{website_url.rstrip('/')}/careers"
            logger.info("Attempting Careers crawl on '%s'...", careers_url)
            careers_content = await self.firecrawl.scrape_url(careers_url)
            if careers_content:
                raw_context.append(f"Careers Page Content:\n{careers_content[:4000]}")

        context_str = "\n\n=== Context Entry ===\n\n".join(raw_context)
        if not context_str.strip():
            logger.warning("No signal data retrieved for %s. Creating blank signals.", company_name)
            return []

        extracted_data = await self._parse_signals_with_llm(company_name, context_str)
        
        stored_signals = []
        
        signals_list = extracted_data.get("signals", [])
        signals_list.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        for sig in signals_list:
            sig_title = sig.get("signal", "Signal Event")
            sig_category = sig.get("category", "Expansion")
            sig_score = float(sig.get("score") or 0.0)
            sig_hook = sig.get("hook", "")
            description = sig.get("description", "")
            
            sig_obj = Signal(
                lead_id=lead_id,
                company_name=company_name,
                signal_type=sig_category.lower().replace(" ", "_"),
                description=description,
                url_source=sig.get("source", website_url or ""),
                signal=sig_title,
                category=sig_category,
                score=sig_score,
                hook=sig_hook,
                growth_indicators=extracted_data.get("growth_indicators", []),
                personalization_angles=extracted_data.get("personalization_angles", []),
                recommended_hooks=extracted_data.get("recommended_hooks", [])
            )
            
            sig_dict = sig_obj.to_dict()
            await db.signals.insert_one(sig_dict)
            sig_dict["id"] = sig_dict.pop("_id")
            stored_signals.append(sig_dict)

            signal_text = (
                f"Company: {company_name}\n"
                f"Signal: {sig_title}\n"
                f"Category: {sig_category}\n"
                f"Score: {sig_score}\n"
                f"Freshness Score: {sig_obj.signal_freshness_score}\n"
                f"Hook: {sig_hook}\n"
                f"Description: {description}"
            )
            await store_document(
                collection_name="signals",
                doc_id=lead_id,
                text=signal_text,
                metadata={
                    "lead_id": lead_id, 
                    "category": sig_category, 
                    "score": sig_score,
                    "freshness_score": sig_obj.signal_freshness_score
                }
            )

        return stored_signals

    async def _parse_signals_with_llm(self, company_name: str, context: str) -> Dict[str, Any]:
        """Utilise UnifiedLLMRouter to parse unstructured news and text into standard JSON."""
        from groq import Groq
        from app.config.settings import settings

        system_prompt = (
            "You are a Signal Intelligence Agent. Your job is to extract business signals from the text context.\n"
            "Categorize signals (e.g. Sales Expansion, Pricing Adjustment, Funding, Tech Stack Update).\n"
            "Score each signal from 0 to 100 based on sales value/urgency, and generate a highly personalized context opener hook."
        )
        
        user_prompt = (
            f"Company Name: {company_name}\n\n"
            f"Context Data:\n{context}\n\n"
            "Extract structured signals. Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            "  \"signals\": [\n"
            "    {\n"
            "      \"signal\": \"Hiring SDRs\",\n"
            "      \"category\": \"Sales Expansion\",\n"
            "      \"score\": 90,\n"
            "      \"hook\": \"Noticed you're expanding your sales team...\",\n"
            "      \"description\": \"Scraped job post details for outbound SDR positions\",\n"
            "      \"source\": \"url\"\n"
            "    }\n"
            "  ],\n"
            "  \"growth_indicators\": [\"...\"],\n"
            "  \"personalization_angles\": [\"...\"],\n"
            "  \"recommended_hooks\": [\"...\"]\n"
            "}"
        )

        def _call_groq(model: str) -> str:
            client = Groq(api_key=settings.GROQ_API_KEY)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content or "{}"

        try:
            response_content = await UnifiedLLMRouter.run_with_fallback(
                role="Signal Intelligence Agent",
                client_call_func=_call_groq
            )
            return json.loads(response_content)
        except Exception as exc:
            logger.error("Failed to parse signals with LLM: %s", exc)
            return {
                "signals": [],
                "growth_indicators": [],
                "personalization_angles": [],
                "recommended_hooks": []
            }

    async def evaluate_opportunity(self, lead_id: str) -> Dict[str, Any]:
        """
        Retrieves company research and signals for a lead,
        runs the Opportunity Intelligence Agent,
        and returns the opportunity analysis.
        """
        db = await get_database()
        
        lead = await db.leads.find_one({"id": lead_id})
        if not lead:
            raise ValueError(f"Lead not found for ID: {lead_id}")
            
        signals = await db.signals.find({"lead_id": lead_id}).to_list(length=100)
        
        company_name = lead.get("company", "Target Company")
        signals_context = ""
        for sig in signals:
            signals_context += (
                f"- Signal: {sig.get('signal')}\n"
                f"  Category: {sig.get('category')}\n"
                f"  Score: {sig.get('score')}\n"
                f"  Freshness Score: {sig.get('signal_freshness_score')}\n"
                f"  Hook: {sig.get('hook')}\n"
                f"  Description: {sig.get('description')}\n\n"
            )
            
        research_context = (
            f"Lead Name: {lead.get('name')}\n"
            f"Job Title/Role: {lead.get('role')}\n"
            f"Company Website: {lead.get('website')}\n"
            f"Discovery Source: {lead.get('discovery_source')}\n"
            f"Lead Quality Score: {lead.get('lead_quality_score', 0.0)}\n"
        )
        
        opportunity_result = await self._run_opportunity_agent_llm(
            company_name, research_context, signals_context
        )
        
        opportunity_doc = {
            "lead_id": lead_id,
            "company_name": company_name,
            "urgency": opportunity_result.get("urgency", "Medium"),
            "best_contact": opportunity_result.get("best_contact", "CTO"),
            "recommended_offer": opportunity_result.get("recommended_offer", "AI Outreach Automation"),
            "confidence_score": opportunity_result.get("confidence_score", 70.0),
            "reasoning": opportunity_result.get("reasoning", ""),
            "evaluated_at": datetime.now(timezone.utc)
        }
        
        await db.opportunities.update_one(
            {"lead_id": lead_id},
            {"$set": opportunity_doc},
            upsert=True
        )
        
        return opportunity_doc

    async def _run_opportunity_agent_llm(
        self, company_name: str, research: str, signals: str
    ) -> Dict[str, Any]:
        """Runs the Opportunity Intelligence Agent LLM prompt."""
        from groq import Groq
        from app.config.settings import settings
        
        system_prompt = (
            "You are an Opportunity Intelligence Agent. Your job is to analyze company research "
            "and scraped signals to identify sales opportunities.\n"
            "Evaluate target contact profiles, sales offers, and assess the sales urgency and confidence score."
        )
        
        user_prompt = (
            f"Company: {company_name}\n\n"
            f"Research Data:\n{research}\n\n"
            f"Scraped Signals:\n{signals}\n\n"
            "Analyze the data and return a JSON object with this schema:\n"
            "{\n"
            "  \"urgency\": \"High|Medium|Low\",\n"
            "  \"best_contact\": \"Persona to target, e.g. CTO/VP of Sales/CEO\",\n"
            "  \"recommended_offer\": \"Tailored outreach value proposition / pitch\",\n"
            "  \"confidence_score\": 85,\n"
            "  \"reasoning\": \"Detailed reasoning of the opportunity evaluation\"\n"
            "}"
        )
        
        def _call_groq(model: str) -> str:
            client = Groq(api_key=settings.GROQ_API_KEY)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content or "{}"
            
        try:
            response_content = await UnifiedLLMRouter.run_with_fallback(
                role="Opportunity Intelligence Agent",
                client_call_func=_call_groq
            )
            return json.loads(response_content)
        except Exception as exc:
            logger.error("Opportunity Agent LLM call failed: %s", exc)
            return {
                "urgency": "Medium",
                "best_contact": "CTO",
                "recommended_offer": "AI Outreach Automation",
                "confidence_score": 50.0,
                "reasoning": "Fallback default opportunity evaluation."
            }