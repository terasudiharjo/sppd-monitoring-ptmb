import os
from dotenv import load_dotenv
from supabase import create_client

# Load credentials dari file .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Cek apakah credentials ke-load
print("🔍 Checking credentials...")
print(f"URL: {SUPABASE_URL[:30]}..." if SUPABASE_URL else "URL: None")
print(f"Key: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "Key: None")

# Test connection
print("\n🔌 Testing connection to Supabase...")
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Connection SUCCESS!")
    print("🎉 Supabase ready to use!")
except Exception as e:
    print(f"❌ Connection FAILED!")
    print(f"Error: {e}")