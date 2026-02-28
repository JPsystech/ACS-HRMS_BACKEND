
import os
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent))

from app.core.config import settings
from app.services.r2_storage import get_r2_storage_service

def list_all():
    try:
        r2 = get_r2_storage_service()
        r2._ensure_client()
        
        response = r2._client.list_objects_v2(Bucket=r2._bucket_name)
        print(f"Listing all objects in '{r2._bucket_name}':")
        
        contents = response.get('Contents', [])
        if not contents:
            print("Bucket is empty.")
        else:
            for obj in contents:
                print(f" - {obj['Key']} ({obj['Size']} bytes)")
                
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    list_all()
