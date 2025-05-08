from fastapi import APIRouter, HTTPException, Query
from supabase_client import supabase
from pydantic import BaseModel, Field
import requests, os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()
api_key = os.getenv("RIOT_API_KEY")
if not api_key:
    raise ValueError("Missing RIOT API KEY")

router = APIRouter(prefix="/summoners", tags=["summoners"])

class SummonerCreate(BaseModel):
    summoner_name: str
    tagline: str = Field(..., description="e.g. 'LEMON' in Simo#LEMON")
    region: str = Field(..., description="e.g. 'europe', 'americas', etc.")

class SummonerProfile(BaseModel):
    puuid: str
    summoner_name: str
    tagline: str
    region: str
    level: Optional[int]
    icon_id: Optional[int]
    last_updated: datetime


# Functions to fetch data from riot api
def get_puuid(summoner_name: str, tagline: str, region: str) -> str:
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}?api_key={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()["puuid"]
    raise HTTPException(status_code=r.status_code, detail="Failed to fetch puuid")

def get_matchIDs(region: str, puuid: str, count: int) -> list:
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&api_key={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    raise HTTPException(status_code=r.status_code, detail="Failed to fetch match IDs")

def get_matchdata(region: str, match_id: str) -> Dict[str,Any]:
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    raise HTTPException(status_code=r.status_code, detail="Failed to fetch match data")

def get_player_matchData(matchData: Dict[str,Any], puuid: str) -> Dict[str,Any]:
    parts = matchData["metadata"]["participants"]
    if puuid not in parts:
        raise HTTPException(status_code=404, detail="PUUID not in match")
    idx = parts.index(puuid)
    return matchData["info"]["participants"][idx]



@router.post("/create-profile", response_model=SummonerProfile)
def create_summoner_profile(summoner: SummonerCreate):
    puuid = get_puuid(summoner.summoner_name, summoner.tagline, summoner.region)

    ids = get_matchIDs(summoner.region.lower(), puuid, 1)
    if not ids:
        raise HTTPException(status_code=404, detail="No recent matches")

    match = get_matchdata(summoner.region.lower(), ids[0])
    player = get_player_matchData(match, puuid)

    payload = {
        "puuid": puuid,
        "summoner_name": player.get("riotIdGameName"),
        "tagline": player.get("riotIdTagline"),
        "region": summoner.region,
        "level": player.get("summonerLevel"),
        "icon_id": player.get("profileIcon"),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    try:
        res = supabase.table("summoner_profiles").insert(payload).execute()
    except Exception as e:
        # Check for duplicate key violation
        if "duplicate key" in str(e) or "violates unique constraint" in str(e):
            raise HTTPException(
                status_code=400,
                detail=f"Summoner '{summoner.summoner_name}#{summoner.tagline}' already exists in this region."
            )
        # Unknown error
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    if not res.data:
        raise HTTPException(
            status_code=500,
            detail=f"Insert failed, no data returned. Full response: {res.__dict__}"
        )

    return SummonerProfile(**res.data[0])