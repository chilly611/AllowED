"""JWT validation and user dependency injection"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger("allowed")

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validate JWT token and return user info including institution_id and role.
    Requires valid Supabase JWT in Authorization header.
    """
    token = credentials.credentials
    from .db import get_supabase

    sb = get_supabase()
    try:
        # Validate token with Supabase admin client
        user_response = sb.auth.get_user(token)
        user = user_response.user

        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Get SCO user record for institution_id and role
        sco_response = sb.table("sco_users").select("*").eq("id", str(user.id)).single().execute()

        if not sco_response.data:
            raise HTTPException(
                status_code=403,
                detail="User not registered as SCO"
            )

        sco_data = sco_response.data
        return {
            "id": str(user.id),
            "email": user.email,
            "institution_id": sco_data["institution_id"],
            "role": sco_data["role"],
            "full_name": sco_data["full_name"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def require_superadmin(user=Depends(get_current_user)):
    """Dependency to enforce superadmin role"""
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user
