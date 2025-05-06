from fastapi import APIRouter, HTTPException, Depends, Query
from dependencies import get_current_user
from supabase_client import supabase
from pydantic import BaseModel, Field
import requests
import os
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")
if not API_KEY:
    raise ValueError("Missing RIOT API KEY in enviroment variables (check .env file)")


router = APIRouter(prefix="summoners", tags=["summoners"])

# MODELS
class SummonerCreate(BaseModel):
    summoner_name: str
    tagline: str = Field(..., description="Riot ID tagline, e.g., 'LEMON' in Simo#LEMON")
    region: str = Field(..., description="Region code, e.g., 'na1', 'euw1', 'me1'...")

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
