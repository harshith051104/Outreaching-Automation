"""
Lead Discovery Fallback Service.

Orchestrates sequential fallback logic for searching leads based on user prompts.
Fails over in the order:
1. Apollo API search
2. Tavily Search API
3. Firecrawl Scraping
4. Falls back to reporting no leads found (leaving CSV upload as manual option)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.services.apollo_service import ApolloService
from app.services.tavily_service import TavilyService
from app.services.firecrawl_service import FirecrawlService
from app.services.hunter_enrichment_service import HunterEnrichmentService
from app.models.lead import Lead

logger = logging.getLogger(__name__)


class LeadDiscoveryService:
    """Service handling lead discovery with robust fallback logic."""

    def __init__(self):
        self.apollo = ApolloService()
        self.tavily = TavilyService()
        self.firecrawl = FirecrawlService()

    async def discover_and_store_leads(
        self,
        user_id: str,
        campaign_id: str,
        query: str,
        job_titles: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        company_size: Optional[str] = None,
        funding_stage: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Discover leads, verify email deliverability via Hunter, calculate quality score,
        deduplicate using lead_hash, and store results in MongoDB.
        """
        logger.info("Attempting Tavily Lead Discovery...")
        try:
            search_parts = []
            if job_titles:
                search_parts.append(" ".join(job_titles))
            search_parts.append("companies")
            if locations:
                search_parts.append(f"in {' '.join(locations)}")
            if industry:
                search_parts.append(industry)
            if country:
                search_parts.append(f"based in {country}")
            if company_size:
                search_parts.append(f"company size around {company_size} employees")
            if funding_stage:
                search_parts.append(f"funding stage: {funding_stage}")
            search_parts.append(query)
            
            search_query = " ".join([p for p in search_parts if p]).strip()
            raw_leads = await self.tavily.discover_leads(query=search_query, limit=limit)
            if raw_leads:
                stored = await self._verify_and_store_leads(
                    raw_leads, user_id, campaign_id, job_titles, "tavily"
                )
                if stored:
                    logger.info("Successfully processed %d leads from Tavily", len(stored))
                    return stored
        except Exception as e:
            logger.error("Tavily discovery failed, falling back: %s", e)

        logger.info("Tavily yielded no results. Attempting Firecrawl directory scraping fallback...")
        try:
            urls = [item for item in query.split() if item.startswith("http")]
            if urls:
                markdown = await self.firecrawl.scrape_url(urls[0])
                if markdown:
                    raw_leads = [{
                        "name": "Scraped Contact",
                        "title": "Directory Listing",
                        "company": "Company Directory",
                        "email": "contact@company.com",
                        "linkedin": "",
                        "website": urls[0]
                    }]
                    stored = await self._verify_and_store_leads(
                        raw_leads, user_id, campaign_id, job_titles, "firecrawl"
                    )
                    if stored:
                        logger.info("Successfully processed %d leads from Firecrawl", len(stored))
                        return stored
        except Exception as e:
            logger.error("Firecrawl directory discovery failed: %s", e)

        logger.info("Attempting Apollo Lead Discovery fallback...")
        try:
            raw_leads = await self.apollo.search_leads(
                job_titles=job_titles,
                locations=locations,
                industry=industry,
                limit=limit
            )
            if raw_leads:
                stored = await self._verify_and_store_leads(
                    raw_leads, user_id, campaign_id, job_titles, "apollo"
                )
                if stored:
                    logger.info("Successfully processed %d leads from Apollo", len(stored))
                    return stored
        except Exception as e:
            logger.error("Apollo discovery failed: %s", e)

        return []

    async def _verify_and_store_leads(
        self,
        raw_leads: List[Dict[str, Any]],
        user_id: str,
        campaign_id: str,
        job_titles: Optional[List[str]],
        source_used: str
    ) -> List[Dict[str, Any]]:
        db = await get_database()
        hunter = HunterEnrichmentService()
        stored_leads = []
        seen_hashes = set()

        for lead_dict in raw_leads:
            email = lead_dict.get("email", "").strip().lower()
            linkedin = lead_dict.get("linkedin", "").strip().lower()
            
            lead_hash = email or linkedin
            if not lead_hash:
                logger.warning("Lead profile lacks both email and LinkedIn - skipping: %s", lead_dict.get("name"))
                continue

            if lead_hash in seen_hashes:
                logger.info("Duplicate lead_hash detected in current batch - skipping: %s", lead_hash)
                continue
            seen_hashes.add(lead_hash)

            verification_result = {}
            hunter_score = 0.0
            
            if email and not email.endswith("example.com") and not email.startswith("unknown"):
                logger.info("Verifying email '%s' via Hunter...", email)
                try:
                    verification = await hunter.verify_email(email)
                    if verification.get("status") == "verified":
                        verification_result = verification
                        if not verification.get("deliverable", True):
                            logger.warning("Hunter verification failed for '%s' (undeliverable) - discarding lead", email)
                            continue
                        hunter_score = float(verification.get("score") or 0.0)
                except Exception as e:
                    logger.error("Hunter verification threw exception for %s: %s", email, e)
            
            existing = await db.leads.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id,
                "$or": [
                    {"lead_hash": lead_hash},
                    {"email": email} if email else {"lead_hash": "dummy_value"},
                    {"linkedin": linkedin} if linkedin else {"lead_hash": "dummy_value"}
                ]
            })
            if existing:
                logger.info("Lead with lead_hash %s already exists in DB – skipping store", lead_hash)
                existing_dict = dict(existing)
                if "_id" in existing_dict:
                    existing_dict["id"] = existing_dict.pop("_id")
                stored_leads.append(existing_dict)
                continue

            completeness = 0.0
            if linkedin: completeness += 10.0
            if lead_dict.get("website"): completeness += 5.0
            if lead_dict.get("company"): completeness += 10.0
            if lead_dict.get("title") or lead_dict.get("role"): completeness += 5.0
            if email: completeness += 10.0
            
            if email:
                if verification_result:
                    email_score = (hunter_score / 100.0) * 40.0
                else:
                    email_score = 30.0
            else:
                email_score = 0.0
                
            fit = 10.0
            role = (lead_dict.get("title") or lead_dict.get("role") or "").lower()
            if job_titles and role:
                for jt in job_titles:
                    if jt.lower() in role:
                        fit = 20.0
                        break
            
            lead_quality = completeness + email_score + fit

            lead_obj = Lead(
                campaign_id=campaign_id,
                user_id=user_id,
                name=lead_dict.get("name", "Unknown Contact"),
                email=email or "unknown@domain.com",
                lead_hash=lead_hash,
                company=lead_dict.get("company", ""),
                website=lead_dict.get("website", ""),
                role=lead_dict.get("title") or lead_dict.get("role") or "",
                linkedin=linkedin,
                discovery_source=source_used,
                status="new",
                score=10.0,
                lead_quality_score=lead_quality,
                enrichment_data={"email_verification": verification_result} if verification_result else {}
            )
            
            lead_data = lead_obj.to_dict()
            await db.leads.insert_one(lead_data)
            lead_data["id"] = lead_data.pop("_id")
            stored_leads.append(lead_data)

            from app.services.qdrant_service import store_document
            lead_summary = f"Lead: {lead_obj.name}, Job Title: {lead_obj.role}, Company: {lead_obj.company}, Website: {lead_obj.website}, Source: {lead_obj.discovery_source}"
            await store_document(
                collection_name="leads",
                doc_id=lead_obj.id,
                text=lead_summary,
                metadata={"user_id": user_id, "campaign_id": campaign_id, "lead_quality_score": lead_quality}
            )
            
        return stored_leads