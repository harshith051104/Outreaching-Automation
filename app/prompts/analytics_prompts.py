"""Analytics prompts for agents."""

ANALYTICS_PROMPT = """Analyze this campaign performance data:

{performance_data}

Provide:
1. Executive summary (one paragraph)
2. Performance grade (A/B/C/D/F)
3. Top 3 wins
4. Top 3 concerns
5. Key recommendations (prioritized by impact)
6. What's working and what's not
"""
