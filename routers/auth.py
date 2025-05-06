from fastapi import APIRouter, HTTPException, Depends, Body
from supabase_client import supabase
from pydantic import BaseModel, EmailStr
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])

class UserCredentials(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    email: EmailStr
    id: str

@router.post("/signup")
async def signup(credentials: UserCredentials):
    try:
        res = supabase.auth.sign_up({
            "email": credentials.email, 
            "password": credentials.password
        })
        
        if res.user:
            return {
                "status": "success", 
                "message": "Signup successful. Check your email for verification",
                "user_id": res.user.id
            }
        raise HTTPException(status_code=400, detail="Signup failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login(credentials: UserCredentials):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": credentials.email, 
            "password": credentials.password
        })
        
        if res.session:
            return {
                "status": "success",
                "access_token": res.session.access_token,
                "refresh_token": res.session.refresh_token,
                "user_id": res.user.id
            }
        raise HTTPException(status_code=401, detail="Login failed")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def get_profile(user = Depends(get_current_user)):
   return {"email": user.email, "id": user.id}