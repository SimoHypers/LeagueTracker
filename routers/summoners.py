from fastapi import APIRouter, HTTPException, Query
from supabase_client import supabase
from pydantic import BaseModel, Field
import requests, os
from typing import Optional, Dict, Any, List
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

class UpdateMatches(BaseModel):
    puuid: str
    region: str


# Functions to fetch data from riot api
def get_puuid(summoner_name: str, tagline: str, region: str) -> str:
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}?api_key={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()["puuid"]
    raise HTTPException(status_code=r.status_code, detail="Failed to fetch puuid")

def get_matchIDs(region: str, puuid: str, count: int, start: int = 0) -> list:
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&api_key={api_key}"
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


def insert_player_matchData(puuid: str, match: Dict[str, Any]):
    player = get_player_matchData(match, puuid)
    match_id = match["metadata"]["matchId"]
    game_start = datetime.fromtimestamp(match["info"]["gameStartTimestamp"] / 1000, tz=timezone.utc)

    # Check if the match already exists for this summoner
    existing_match = supabase.table("player_matches").select("id").eq("puuid", puuid).eq("match_id", match_id).execute()
    if existing_match.data:
        # Match already exists for this summoner, skip insertion
        return existing_match.data[0]
    
    # Now check if the match exists in the database (for any summoner)
    match_exists = supabase.table("player_matches").select("id").eq("match_id", match_id).execute()
    
    summoner_res = supabase.table("summoner_profiles").select("id").eq("puuid", puuid).execute()
    if not summoner_res.data:
        raise HTTPException(status_code=404, detail="Summoner profile not found")
    summoner_profile_id = summoner_res.data[0]["id"]

    payload = {
        "match_id": match_id,
        "puuid": puuid,
        "win": player.get("win"),
        "role": player.get("role"),
        "kills": player.get("kills"),
        "deaths": player.get("deaths"),
        "assists": player.get("assists"),
        "team_id": player.get("teamId"),
        "game_start": game_start.isoformat(),
        "summoner_profile_id": summoner_profile_id,
        "riotid_gamename": player.get("riotIdGameName"),
        "riotid_tagline": player.get("riotIdTagline"),
        "summoner_level": player.get("summonerLevel"),
        "champion_name": player.get("championName"),
        "total_damagedealttochampions": player.get("totalDamageDealtToChampions"),
        "enemy_missing_pings": player.get("enemyMissingPings"),
        "gold_earned": player.get("goldEarned"),
        "damage_per_minute": player.get("challenges", {}).get("damagePerMinute"),
        "skillshot_dodged": player.get("challenges", {}).get("skillshotsDodged"),
        "skillshot_hit": player.get("challenges", {}).get("skillshotsHit"),
        "damage_dealt_to_turrets": player.get("damageDealtToTurrets"),
        "longest_time_living": player.get("longestTimeSpentLiving"),
        "game_ended_in_surrender": player.get("gameEndedInSurrender"),
        "team_early_surrendered": player.get("teamEarlySurrendered")
    }

    try:
        insert_res = supabase.table("player_matches").insert(payload).execute()

        if not insert_res.data:
            raise HTTPException(status_code=500, detail=f"Failed to insert player match data. Response: {insert_res.__dict__}")
        return insert_res.data[0]
    except Exception as e:
        print(f"Error processing match {match_id}: {str(e)}")
        # Return existing match data if possible
        if match_exists and match_exists.data:
            return match_exists.data[0]
        return {"match_id": match_id, "error": str(e)}



@router.post("/create-profile", response_model=SummonerProfile)
def create_summoner_profile(summoner: SummonerCreate):
    try:
        puuid = get_puuid(summoner.summoner_name, summoner.tagline, summoner.region)
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=f"Failed to find summoner: {e.detail}")

    # Check if profile already exists
    existing_profile = supabase.table("summoner_profiles").select("*").eq("puuid", puuid).execute()
    
    if existing_profile.data:
        # Profile exists, just return it without fetching matches
        # Update existing profile with current timestamp
        update_data = {
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        update_res = supabase.table("summoner_profiles").update(update_data).eq("puuid", puuid).execute()
        profile = update_res.data[0]
    else:
        # Create new profile
        profile_data = {
            "puuid": puuid,
            "summoner_name": summoner.summoner_name,
            "tagline": summoner.tagline,
            "region": summoner.region,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        insert_res = supabase.table("summoner_profiles").insert(profile_data).execute()
        if not insert_res.data:
            raise HTTPException(status_code=500, detail="Failed to create summoner profile")
        profile = insert_res.data[0]

        # Only fetch matches for new profiles
        try:
            match_ids = get_matchIDs(summoner.region.lower(), puuid, 5)
            # Process recent matches
            for match_id in match_ids:
                try:
                    match_data = get_matchdata(summoner.region.lower(), match_id)
                    insert_player_matchData(puuid, match_data)
                except Exception as e:
                    # Log but continue with other matches
                    print(f"Error processing match {match_id}: {str(e)}")
        except Exception as e:
            print(f"Error fetching matches, but continuing: {str(e)}")
    
    return SummonerProfile(**profile)


@router.get("/profile/{puuid}", response_model=SummonerProfile)
def get_summoner_profile(puuid: str):
    result = supabase.table("summoner_profiles").select("*").eq("puuid", puuid).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Summoner profile not found")
        
    return SummonerProfile(**result.data[0])


@router.get("/profiles", response_model=List[SummonerProfile])
def get_all_summoner_profiles():
    result = supabase.table("summoner_profiles").select("*").execute()
    
    if not result.data:
        return []
        
    return [SummonerProfile(**profile) for profile in result.data]


@router.post("/update-matches")
def update_summoner_matches(update: UpdateMatches):
    # Verify summoner exists
    profile_res = supabase.table("summoner_profiles").select("*").eq("puuid", update.puuid).execute()
    
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Summoner profile not found")
    
    # Get latest 10 matches instead of 20 to reduce load
    try:
        match_ids = get_matchIDs(update.region.lower(), update.puuid, 10)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch match IDs: {str(e)}")
    
    updated_matches = []
    for match_id in match_ids:
        try:
            # First check if we already have this match for this summoner
            existing = supabase.table("player_matches").select("id").eq("puuid", update.puuid).eq("match_id", match_id).execute()
            if existing.data:
                continue  # Skip if already exists
                
            match_data = get_matchdata(update.region.lower(), match_id)
            match_result = insert_player_matchData(update.puuid, match_data)
            updated_matches.append(match_id)
        except Exception as e:
            # Log but continue with other matches
            print(f"Error processing match {match_id}: {str(e)}")
    
    # Update last_updated timestamp
    update_data = {
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("summoner_profiles").update(update_data).eq("puuid", update.puuid).execute()
    
    return {"message": f"Updated {len(updated_matches)} matches", "updated_matches": updated_matches}


@router.get("/matches/{puuid}")
def get_summoner_matches(puuid: str, limit: int = Query(20, ge=1, le=100)):
    # Verify summoner exists
    profile_res = supabase.table("summoner_profiles").select("id").eq("puuid", puuid).execute()
    
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Summoner profile not found")
    
    # Get matches
    matches_res = supabase.table("player_matches").select("*").eq("puuid", puuid).order("game_start", desc=True).limit(limit).execute()
    
    if not matches_res.data:
        return []
    
    return matches_res.data


@router.delete("/profile/{puuid}")
def delete_summoner_profile(puuid: str):
    # First delete all matches
    matches_res = supabase.table("player_matches").delete().eq("puuid", puuid).execute()
    
    # Then delete the profile
    profile_res = supabase.table("summoner_profiles").delete().eq("puuid", puuid).execute()
    
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Summoner profile not found")
    
    return {"message": "Summoner profile and all matches deleted"}


@router.get("/stats/{puuid}")
def get_summoner_stats(puuid: str):
    # Verify summoner exists
    profile_res = supabase.table("summoner_profiles").select("*").eq("puuid", puuid).execute()
    
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Summoner profile not found")
    
    # Get matches
    matches_res = supabase.table("player_matches").select("*").eq("puuid", puuid).execute()
    
    if not matches_res.data:
        return {"matches_count": 0, "message": "No matches found"}
    
    matches = matches_res.data
    total_matches = len(matches)
    wins = sum(1 for match in matches if match.get("win") is True)
    losses = total_matches - wins
    
    # Calculate KDA
    total_kills = sum(match.get("kills", 0) for match in matches)
    total_deaths = sum(match.get("deaths", 0) for match in matches)
    total_assists = sum(match.get("assists", 0) for match in matches)
    
    avg_kills = total_kills / total_matches if total_matches > 0 else 0
    avg_deaths = total_deaths / total_matches if total_matches > 0 else 0
    avg_assists = total_assists / total_matches if total_matches > 0 else 0
    
    kda = (total_kills + total_assists) / total_deaths if total_deaths > 0 else (total_kills + total_assists)
    
    # Calculate champion statistics
    champion_stats = {}
    for match in matches:
        champion = match.get("champion_name")
        if not champion:
            continue
            
        if champion not in champion_stats:
            champion_stats[champion] = {
                "games": 0,
                "wins": 0,
                "kills": 0,
                "deaths": 0, 
                "assists": 0
            }
            
        stats = champion_stats[champion]
        stats["games"] += 1
        if match.get("win"):
            stats["wins"] += 1
        stats["kills"] += match.get("kills", 0)
        stats["deaths"] += match.get("deaths", 0)
        stats["assists"] += match.get("assists", 0)
    
    # Calculate win rates and KDAs for champions
    for champion, stats in champion_stats.items():
        stats["win_rate"] = (stats["wins"] / stats["games"]) * 100 if stats["games"] > 0 else 0
        stats["kda"] = (stats["kills"] + stats["assists"]) / stats["deaths"] if stats["deaths"] > 0 else (stats["kills"] + stats["assists"])
        stats["avg_kills"] = stats["kills"] / stats["games"] if stats["games"] > 0 else 0
        stats["avg_deaths"] = stats["deaths"] / stats["games"] if stats["games"] > 0 else 0
        stats["avg_assists"] = stats["assists"] / stats["games"] if stats["games"] > 0 else 0
    
    return {
        "summoner": profile_res.data[0],
        "overall_stats": {
            "matches_played": total_matches,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total_matches) * 100 if total_matches > 0 else 0,
            "kda": kda,
            "avg_kills": avg_kills,
            "avg_deaths": avg_deaths,
            "avg_assists": avg_assists
        },
        "champion_stats": champion_stats
    }