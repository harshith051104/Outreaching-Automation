import logging
import json
from typing import Dict, Any
from app.agents.tools.email_tool import EmailAnalysisTool

logger = logging.getLogger(__name__)

async def spam_check(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    tool = EmailAnalysisTool()
    result = tool._run(
        email_content=inputs.get("email_content", ""),
        subject=inputs.get("subject", ""),
    )
    try:
        return json.loads(result)
    except Exception:
        return {"raw_output": result}

def register_spam_tools(dispatcher: Any) -> None:
    dispatcher.register("spam_check", spam_check)
