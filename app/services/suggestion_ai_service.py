"""
AI service for enhancing platform suggestions.
"""

import json
import logging
from app.config.mongodb_config import get_database
from app.config.llm_router import UnifiedLLMRouter

logger = logging.getLogger(__name__)


async def enhance_suggestion_with_ai(suggestion_id: str) -> None:
    """
    Asynchronously queries Groq (via UnifiedLLMRouter) to generate AI Summary,
    Priority, Business Impact, and a Suggested Category, updating the MongoDB suggestion.
    """
    try:
        db = await get_database()
        suggestion = await db.suggestions.find_one({"_id": suggestion_id})
        if not suggestion:
            logger.error(f"Suggestion {suggestion_id} not found for AI enhancement.")
            return

        title = suggestion.get("title", "")
        description = suggestion.get("description", "")

        system_prompt = (
            "You are an AI Product Manager assistant.\n"
            "Your task is to analyze user feedback/suggestions and generate structured metadata.\n"
            "Provide a concise 1-sentence summary, suggest a category, estimate the priority, and analyze the business impact.\n"
            "Respond ONLY with a valid JSON object matching the requested schema."
        )

        user_prompt = f"""
        Analyze the following user suggestion:
        Title: {title}
        Description: {description}

        Return exactly a JSON object matching this schema:
        {{
            "summary": "Concise 1-sentence summary of the feedback",
            "suggested_category": "feature_request | improvement | suggestion | feedback | bug_report",
            "priority": "low | medium | high | critical",
            "business_impact": "Short sentence explaining the business impact or user value of this suggestion"
        }}
        """

        from groq import Groq
        from app.config.settings import settings

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

        # Run with unified LLM router
        response_content = await UnifiedLLMRouter.run_with_fallback(
            role="analytics",  # utilizing the analytics LLM fallback profile
            client_call_func=_call_groq
        )

        try:
            data = json.loads(response_content)
        except Exception:
            logger.error(f"Failed to parse AI response as JSON for suggestion {suggestion_id}: {response_content}")
            return

        ai_summary = data.get("summary", "")
        ai_priority = data.get("priority", "medium")
        ai_business_impact = data.get("business_impact", "")
        ai_suggested_category = data.get("suggested_category", suggestion.get("category"))

        update_fields = {
            "ai_summary": ai_summary,
            "ai_priority": ai_priority,
            "ai_business_impact": ai_business_impact,
            "ai_suggested_category": ai_suggested_category,
            "updated_at": suggestion.get("updated_at")  # preserve update time or let it stand
        }

        await db.suggestions.update_one(
            {"_id": suggestion_id},
            {"$set": update_fields}
        )
        logger.info(f"Successfully enhanced suggestion {suggestion_id} with AI metrics.")

    except Exception as e:
        logger.exception(f"Error during AI enhancement for suggestion {suggestion_id}: {e}")
