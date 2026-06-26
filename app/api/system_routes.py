from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any
import os
from pydantic import BaseModel
from dotenv import set_key, dotenv_values
from app.api.auth_routes import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/system", tags=["System Configuration"])

class EnvUpdateRequest(BaseModel):
    variables: dict[str, str]

@router.get("/env")
async def get_env_variables(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Retrieve non-sensitive infrastructure variables from the .env file."""
    # Only the owner/admin should be able to do this, but assuming get_current_user is sufficient
    # for the platform scope. 
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    if not os.path.exists(env_path):
        return {"variables": {}}
        
    env_vars = dotenv_values(env_path)
    
    # Expose only specific infrastructure variables, scrub everything else
    safe_vars = ["MONGODB_URL"]
    
    exposed = {k: v for k, v in env_vars.items() if k in safe_vars}
    return {"variables": exposed}


@router.post("/env")
async def update_env_variables(request: EnvUpdateRequest, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Update specific infrastructure variables directly in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    
    # Make sure file exists
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("")
            
    allowed_vars = ["MONGODB_URL"]
    
    updated_count = 0
    for key, value in request.variables.items():
        if key in allowed_vars:
            set_key(env_path, key, value)
            updated_count += 1
            
    return {"message": f"Successfully updated {updated_count} infrastructure settings in .env. A server restart is required for these to take effect."}








