from supabase_client import supabase
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from routers import auth, summoners
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # LATER REPLACE WITH SPECIFIC ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "data": None, "error": None})

@app.post("/", response_class=HTMLResponse)
async def search_summoner(request: Request, summoner_name: str = Form(...)):
    response = supabase.table("summoner_profiles").select("*").eq("summoner_name", summoner_name).execute()

    if not response.data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "data": None,
            "error": "Summoner not found"
        })
    
    summoner = response.data[0]
    puuid = summoner["puuid"]

    match_response = supabase.table("player_matches").select("match_id").eq("puuid", puuid).execute()
    match_ids = [match["match_id"] for match in match_response.data]

    data = {
        "summoner_name": summoner["summoner_name"],
        "matches": match_ids
    }

    return templates.TemplateResponse("index.html", {"request": request, "data": data, "error": None})

#Including Routers
app.include_router(auth.router)
app.include_router(summoners.router)




