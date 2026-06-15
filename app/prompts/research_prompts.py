"""Research agent prompt templates for CrewAI agents."""

LEAD_RESEARCH_PROMPT = """Research the following lead and their company.

Lead Name: {lead_name}
Company: {company}
Role: {role}
Website: {website}

Provide a structured report with:
- Company description and industry
- Recent news or developments
- Company size and technology stack
- Key decision makers
- Potential pain points for {role} at {company}
- Personalization hooks for outreach
"""


COMPANY_RESEARCH_PROMPT = """Research the company {company}.

Find:
1. What they do and their market position
2. Recent news, funding, or product launches
3. Company size and growth trajectory
4. Technology stack they use
5. Key competitors
6. Potential reasons they'd need your solution
"""