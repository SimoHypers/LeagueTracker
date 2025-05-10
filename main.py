from supabase_client import supabase
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from routers import auth, summoners
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import httpx

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

# Valid regions for dropdown selection
REGIONS = {
    "EUW1": "europe",
    "ME1": "europe",
    "NA1": "americas",
    "KR": "asia",
    "BR1": "americas",
    "LA1": "americas",
    "LA2": "americas",
    "JP1": "asia",
    "EUN1": "europe",
    "TR1": "europe",
    "RU": "europe",
    "OC1": "sea"
}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "data": None, 
        "error": None,
        "regions": REGIONS
    })

@app.post("/submit-summoner", response_class=HTMLResponse)
async def submit_summoner(request: Request,
                          summoner_name: str = Form(...),
                          tagline: str = Form(...),
                          region: str = Form(...)):
    
    # Get the actual region code from selected region
    region_code = REGIONS.get(region)
    if not region_code:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Invalid region selected",
            "regions": REGIONS
        })
    
    payload = {
        "summoner_name": summoner_name,
        "tagline": tagline,
        "region": region_code
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("http://localhost:8000/summoners/create-profile", json=payload)

            if response.status_code == 200:
                # Redirect to the summoner profile page after successful creation
                return RedirectResponse(url=f"/summoner/{summoner_name}/{tagline}/{region}", status_code=303)
            elif response.status_code == 400:
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "error": response.json().get("detail", "Summoner already exists"),
                    "regions": REGIONS
                })
            else:
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "error": f"Unexpected error: {response.text}",
                    "regions": REGIONS
                })
            
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Request failed: {str(e)}",
            "regions": REGIONS
        })

@app.get("/api/matches/{summoner_name}/{tagline}/{region}")
async def get_more_matches(summoner_name: str, tagline: str, region: str, offset: int = 0, limit: int = 10):
    try:
        # First get the summoner profile data to get the puuid
        response = supabase.table("summoner_profiles").select("puuid").eq("summoner_name", summoner_name).eq("tagline", tagline).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Summoner not found")
        
        puuid = response.data[0]["puuid"]

        # Get additional matches with pagination
        match_response = supabase.table("player_matches").select("*").eq("puuid", puuid).order("game_start", desc=True).range(offset, offset + limit - 1).execute()
        
        return {"matches": match_response.data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/refresh-summoner/{summoner_name}/{tagline}/{region}", response_class=HTMLResponse)
async def refresh_summoner_data(request: Request, summoner_name: str, tagline: str, region: str):
    try:
        # Call the Riot API to refresh data
        region_code = REGIONS.get(region)
        if not region_code:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "error": "Invalid region",
                "regions": REGIONS
            })
        
        payload = {
            "summoner_name": summoner_name,
            "tagline": tagline,
            "region": region_code
        }
        
        async with httpx.AsyncClient() as client:
            # Get the PUUID first
            summoner_response = supabase.table("summoner_profiles").select("puuid").eq("summoner_name", summoner_name).eq("tagline", tagline).execute()
            if not summoner_response.data:
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "error": "Summoner not found",
                    "regions": REGIONS
                })
            
            puuid = summoner_response.data[0]["puuid"]
            
            # Update the last_updated timestamp
            supabase.table("summoner_profiles").update({"last_updated": "now()"}).eq("puuid", puuid).execute()
            
            # Get new matches from Riot API
            response = await client.post(f"http://localhost:8000/summoners/update-matches", json={
                "puuid": puuid,
                "region": region_code
            })
            
            if response.status_code != 200:
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "error": f"Failed to refresh data: {response.text}",
                    "regions": REGIONS
                })
            
            # Redirect back to the summoner profile
            return RedirectResponse(url=f"/summoner/{summoner_name}/{tagline}/{region}", status_code=303)
    
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Error refreshing data: {str(e)}",
            "regions": REGIONS
        })

@app.get("/summoner/{summoner_name}/{tagline}/{region}", response_class=HTMLResponse)
async def get_summoner_profile(request: Request, summoner_name: str, tagline: str, region: str):
    try:
        # First get the summoner profile data
        response = supabase.table("summoner_profiles").select("*").eq("summoner_name", summoner_name).eq("tagline", tagline).execute()

        if not response.data:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "data": None,
                "error": "Summoner not found",
                "regions": REGIONS
            })
        
        summoner = response.data[0]
        puuid = summoner["puuid"]

        # Get match data with more details
        match_response = supabase.table("player_matches").select("*").eq("puuid", puuid).order("game_start", desc=True).limit(20).execute()
        
        matches = match_response.data

        summoner_data = {
            "summoner": summoner,
            "matches": matches,
            # Calculate some stats
            "total_matches": len(matches),
            "win_rate": calculate_win_rate(matches) if matches else 0,
            "avg_kda": calculate_avg_kda(matches) if matches else {"kills": 0, "deaths": 0, "assists": 0},
            "most_played_champions": get_most_played_champions(matches) if matches else []
        }

        return templates.TemplateResponse("summoner.html", {
            "request": request, 
            "data": summoner_data,
            "error": None,
            "regions": REGIONS
        })
    
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "data": None,
            "error": f"Error fetching summoner data: {str(e)}",
            "regions": REGIONS
        })

@app.get("/match/{match_id}", response_class=HTMLResponse)
async def get_match_details(request: Request, match_id: str):
    try:
        # Get all players from this match
        match_response = supabase.table("player_matches").select("*").eq("match_id", match_id).execute()
        
        if not match_response.data:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "data": None,
                "error": "Match not found",
                "regions": REGIONS
            })
        
        # Organize players by team
        teams = {
            "blue": [],
            "red": []
        }
        
        for player in match_response.data:
            team = "blue" if player["team_id"] == 100 else "red"
            teams[team].append(player)
        
        # Get general match info from first player
        match_info = {
            "id": match_id,
            "game_start": match_response.data[0]["game_start"],
            "teams": teams,
            "winner": "blue" if teams["blue"] and teams["blue"][0]["win"] else "red"
        }
        
        return templates.TemplateResponse("match.html", {
            "request": request,
            "match": match_info,
            "regions": REGIONS
        })
    
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "data": None,
            "error": f"Error fetching match data: {str(e)}",
            "regions": REGIONS
        })

# Helper functions for stats
def calculate_win_rate(matches: List[Dict[str, Any]]) -> float:
    if not matches:
        return 0
    wins = sum(1 for match in matches if match["win"])
    return round((wins / len(matches)) * 100, 1)

def calculate_avg_kda(matches: List[Dict[str, Any]]) -> Dict[str, float]:
    if not matches:
        return {"kills": 0, "deaths": 0, "assists": 0, "ratio": 0}
    
    total_kills = sum(match["kills"] for match in matches if match.get("kills") is not None)
    total_deaths = sum(match["deaths"] for match in matches if match.get("deaths") is not None)
    total_assists = sum(match["assists"] for match in matches if match.get("assists") is not None)
    
    count = len(matches)
    # Use max(1, total_deaths) to avoid division by zero
    return {
        "kills": round(total_kills / count, 1) if count > 0 else 0,
        "deaths": round(total_deaths / count, 1) if count > 0 else 0,
        "assists": round(total_assists / count, 1) if count > 0 else 0,
        "ratio": round((total_kills + total_assists) / max(1, total_deaths), 2) if total_deaths > 0 else round(total_kills + total_assists, 2)
    }

def get_most_played_champions(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not matches:
        return []
    
    champion_counts = {}
    for match in matches:
        champion = match.get("champion_name")
        if champion:
            if champion in champion_counts:
                champion_counts[champion]["count"] += 1
                if match["win"]:
                    champion_counts[champion]["wins"] += 1
            else:
                champion_counts[champion] = {
                    "name": champion,
                    "count": 1,
                    "wins": 1 if match["win"] else 0
                }
    
    # Convert to list and sort by count
    champions_list = list(champion_counts.values())
    champions_list.sort(key=lambda x: x["count"], reverse=True)
    
    # Add win rate
    for champion in champions_list:
        champion["win_rate"] = round((champion["wins"] / champion["count"]) * 100, 1)
    
    return champions_list[:5]  # Return top 5 most played

#Including Routers
app.include_router(auth.router)
app.include_router(summoners.router)