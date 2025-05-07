# Existing imports and setup...
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from dependencies import get_current_user
from supabase_client import supabase
from pydantic import BaseModel, Field
import requests
import os
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timezone

load_dotenv()

api_key = os.getenv("RIOT_API_KEY")
if not api_key:
    raise ValueError("Missing RIOT API KEY in enviroment variables (check .env file)")

router = APIRouter(prefix="/summoners", tags=["summoners"])

# MODELS
class SummonerCreate(BaseModel):
    summoner_name: str
    tagline: str = Field(..., description="Riot ID tagline, e.g., 'LEMON' in Simo#LEMON")
    region: str = Field(..., description="Region map, e.g., AMERICAS, EUROPE...")

class SummonerResponse(BaseModel):
    id: str
    summoner_name: str
    tagline: str
    region: str
    user_id: str
    puuid: Optional[str] = None
    level: Optional[int] = None
    icon_id: Optional[int] = None

class Match(BaseModel):
    id: int
    match_id: str
    puuid: str
    riotid_gamename: Optional[str]
    riotid_tagline: Optional[str]
    summoner_level: Optional[int]
    win: Optional[bool]
    champion_name: Optional[str]
    role: Optional[str]
    kills: Optional[int]
    deaths: Optional[int]
    assists: Optional[int]
    total_damagedealttochampions: Optional[int]
    enemy_missing_pings: Optional[int]
    gold_earned: Optional[int]
    damage_per_minute: Optional[int]
    skillshot_dodged: Optional[int]
    skillshot_hit: Optional[int]
    damage_dealt_to_turrets: Optional[int]
    longest_time_living: Optional[int]
    game_ended_in_surrender: Optional[bool]
    team_early_surrendered: Optional[bool]
    team_id: Optional[int]
    game_start: Optional[datetime]
    summoner_profile_id: Optional[int]

@router.post("/create-profile")
def create_summoner_profile(
    summoner: SummonerCreate,
    user = Depends(get_current_user)
):
    puuid = get_puuid(summoner.summoner_name, summoner.tagline, summoner.region)
    match_ids = get_matchIDs(summoner.region.lower(), puuid, 1)
    match_data = get_matchdata(summoner.region.lower(), match_ids[0])
    player_data = get_player_matchData(match_data, puuid)

    # Insert into Supabase using the logged-in user's ID
    insert_response = insert_summoner_profiles(
        player_data=player_data,
        user_id=user.id,
        region=summoner.region
    )

    return {"status": "success", "inserted": insert_response.data}


# FUNCTIONS
def get_puuid(summoner_name: str, tagline: str, region_map: str) -> str:
    api_url = f'https://{region_map}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}?api_key={api_key}'
    response = requests.get(api_url)
    if response.status_code == 200:
        user_info = response.json()
        return user_info['puuid']
    else:
        print(f"Error: {response.status_code}")
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch puuid")

def get_matchIDs(region, puuid, no_matches):
    api_url = f'https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={no_matches}&api_key={api_key}'
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch match IDs")

def get_matchdata(region, matchID):
    api_url = f'https://{region}.api.riotgames.com/lol/match/v5/matches/{matchID}?api_key={api_key}'
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch match data")

def get_player_matchData(matchData, player_puuid):
    try:
        participants = matchData['metadata']['participants']
        index = participants.index(player_puuid)
        return matchData['info']['participants'][index]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract player data: {e}")

# ROUTES
@router.get("/puuid")
def fetch_puuid(
    summoner_name: str = Query(..., example="Simo"),
    tagline: str = Query(..., example="LEMON"),
    region_map: str = Query(..., example="EUROPE")
):
    puuid = get_puuid(summoner_name, tagline, region_map)
    return {"puuid": puuid}


@router.get("/match-ids")
def fetch_match_ids(
    region: str = Query(..., example="europe"),
    puuid: str = Query(..., example="some-puuid"),
    count: int = Query(5, ge=1, le=100),
):
    match_ids = get_matchIDs(region, puuid, count)
    return {"match_ids": match_ids}


@router.get("/match-data")
def fetch_match_data(
    region: str = Query(..., example="europe"),
    match_id: str = Query(..., example="EUW1_1234567890"),
):
    match_data = get_matchdata(region, match_id)
    return {"match_data": match_data}


@router.get("/match/playerdata")
def fetch_player_match_data(
    match_id: str = Query(...),
    region: str = Query(...),
    player_puuid: str = Query(...)
):
    try:
        match_data = get_matchdata(region, match_id)
        player_data = get_player_matchData(match_data, player_puuid)
        return player_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/test-insert")
def test_insert_summoner_profile(
    summoner_name: str = Body(...),
    tagline: str = Body(...),
    region: str = Body(...),
    user_id: str = Body(...),
):
    # Step 1: Get PUUID
    puuid = get_puuid(summoner_name, tagline, region)

    # Step 2: Get a match ID (any recent one, or just one to get player data)
    match_ids = get_matchIDs(region, puuid, 1)
    if not match_ids:
        raise HTTPException(status_code=404, detail="No matches found.")

    # Step 3: Get match data and player data
    match_data = get_matchdata(region, match_ids[0])
    player_data = get_player_matchData(match_data, puuid)

    # Step 4: Insert to Supabase
    result = insert_summoner_profiles(player_data, user_id, region)
    return {"status": "inserted", "response": result.data}



# Inserting data into SUPABASE
def insert_summoner_profiles(player_data: dict, user_id:  str, region: str):
    try:
        response = supabase.table("summoner_profiles").insert({
            "user_id": user_id,
            "summoner_name": player_data.get("riotIdGameName"),
            "tagline": player_data.get("riotIdTagline"),
            "puuid": player_data.get("puuid"),
            "region": region,
            "level": player_data.get("summonerLevel"),
            "icon_id": player_data.get("profileIcon"),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }).execute()

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert into Supabase: {e}")
