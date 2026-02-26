import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from main import get_watch_url_from_supabase

# Load env vars
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_url():
    movie_title = "Marty Supreme"
    print(f"Testing URL fetch for: {movie_title}")
    
    # Check env vars
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    print(f"Supabase URL: {url}")
    print(f"Supabase Key: {key[:5]}..." if key else "None")
    
    if not url or not key:
        print("Missing credentials!")
        return

    # Call the function
    try:
        watch_url = get_watch_url_from_supabase(movie_title)
        print(f"Result URL: {watch_url}")
    except Exception as e:
        print(f"Error calling function: {e}")

    # Manual test with fixed logic to verify
    print("\n--- Manual Query Test ---")
    client = create_client(url, key)
    
    try:
        print("INSPECTING SCHEMA:")
        res = client.table('movies').select('*').limit(1).execute()
        if res.data:
            print("Columns found:", res.data[0].keys())
            print("First row sample:", res.data[0])
        else:
            print("No data found in movies table.")
    except Exception as e:
        print(f"Schema inspection failed: {e}")

    try:
        print("1. Exact match with quotes (CORRECTED COLUMNS):")
        query = f'title.eq."{movie_title}",arabic_title.eq."{movie_title}",original_title.eq."{movie_title}"'
        res = client.table('movies').select('id, title, arabic_title, slug').or_(query).limit(1).execute()
        print(f"Result: {res.data}")
    except Exception as e:
        print(f"Failed: {e}")
        
    try:
        print("2. ILIKE match (title):")
        res = client.table('movies').select('id, title, arabic_title, slug').ilike('title', f"%{movie_title}%").limit(1).execute()
        print(f"Result: {res.data}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_url()
