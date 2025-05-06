from fastapi import Depends, HTTPException, Header
from typing import Optional
from supabase_client import supabase

async def get_current_user(authorization: Optional[str] = Header(None, convert_underscores=True)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        token = authorization[7:]  # Strip "Bearer "
        user = supabase.auth.get_user(token)
        print("User:", user)

        if not user.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return user.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")
