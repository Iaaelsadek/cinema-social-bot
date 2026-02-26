
import os
from supabase import create_client

url = "https://lhpuwupbhpcqkwqugkhh.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxocHV3dXBiaHBjcWt3cXVna2hoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA5MDkyODgsImV4cCI6MjA4NjQ4NTI4OH0.QCYzJaWo0mmFQwZjwaNjIJR1jR4wOb4CbqTKxTAaO2w"

client = create_client(url, key)

try:
    print("Fetching series...")
    res = client.table('series').select('*').limit(1).execute()
    if res.data:
        print("Series columns:", res.data[0].keys())
    else:
        print("No series found.")
except Exception as e:
    print("Error:", e)
