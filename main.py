from supabase_client import supabase
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from routers import auth, summoners

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # LATER REPLACE WITH SPECIFIC ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "League Tracker API is up and running"}

#Including Routers
app.include_router(auth.router)
app.include_router(summoners.router)





#data = supabase.table("test").insert({"test":"testing 12345"}).execute()
#data = supabase.table("test").select("*").execute()
#print(data)

#data = supabase.table("test").delete().eq("id", 2).execute()
#print(data)

