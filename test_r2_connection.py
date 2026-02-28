
import os
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent))

from app.core.config import settings
from app.services.r2_storage import get_r2_storage_service

def test_r2():
    print(f"R2_ENDPOINT: {settings.R2_ENDPOINT}")
    print(f"R2_ACCESS_KEY_ID: {settings.R2_ACCESS_KEY_ID}")
    print(f"R2_SECRET_ACCESS_KEY: {'*' * len(settings.R2_SECRET_ACCESS_KEY) if settings.R2_SECRET_ACCESS_KEY else 'None'}")
    print(f"R2_BUCKET: {settings.R2_BUCKET}")
    
    try:
        r2 = get_r2_storage_service()
        # Try a simple operation like listing objects or just checking the client
        r2._ensure_client()
        print("R2 client initialized successfully.")
        
        # Try to list objects (first 1)
        response = r2._client.list_objects_v2(Bucket=r2._bucket_name, MaxKeys=1)
        print(f"Successfully connected to R2 bucket '{r2._bucket_name}'.")
        print(f"Found {len(response.get('Contents', []))} objects (limited to 1).")
        
    except Exception as e:
        print(f"R2 test failed: {e}")

if __name__ == "__main__":
    test_r2()
