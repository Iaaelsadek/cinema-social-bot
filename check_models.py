import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in .env")
else:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("Listing available models (google-genai SDK):")
        # The new SDK might handle listing differently or not support it directly in the same way.
        # But let's try to find a way or just test the model we want.
        
        # Actually, let's just test 'gemini-1.5-flash' directly to see if it works.
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents='Hello, world!'
            )
            print(f"Success! Model 'gemini-1.5-flash' is working. Response: {response.text}")
        except Exception as e:
            print(f"Error testing 'gemini-1.5-flash': {e}")
            
        # Try listing if possible (documentation varies, but let's try standard approach if known)
        # client.models.list() might be the way.
        try:
            for m in client.models.list():
                print(f"- {m.name}")
        except Exception as e:
            print(f"Could not list models: {e}")

    except Exception as e:
        print(f"Error initializing client: {e}")
