import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)