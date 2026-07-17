"""
Campaign Execution, Personalization & Template Compilation Runtime.

Modular architecture for email generation pipeline:
Research -> Personalization -> Placeholder Resolution -> Validation -> Compilation -> EmailArtifact

Campaign Runtime orchestrates only. Never generates email content.
"""

from campaigns.runtime import CampaignRuntime
from campaigns.pipeline import compile_email
from campaigns.artifacts import ResearchArtifact, PersonalizationArtifact, EmailArtifact

__all__ = ["CampaignRuntime", "compile_email", "ResearchArtifact", "PersonalizationArtifact", "EmailArtifact"]
