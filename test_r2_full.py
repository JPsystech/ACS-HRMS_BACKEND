
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent))

# Load .env explicitly for comparison
load_dotenv(".env")

from app.core.config import settings
from app.services.r2_storage import get_r2_storage_service

def test_r2():
    print(f"--- OS Environ ---")
    print(f"R2_ENDPOINT (os): {os.environ.get('R2_ENDPOINT')}")
    print(f"R2_ACCESS_KEY_ID (os): {os.environ.get('R2_ACCESS_KEY_ID')}")
    print(f"R2_BUCKET (os): {os.environ.get('R2_BUCKET')}")
    
    print(f"\n--- Pydantic Settings ---")
    print(f"R2_ENDPOINT: {settings.R2_ENDPOINT}")
    print(f"R2_ACCESS_KEY_ID: {settings.R2_ACCESS_KEY_ID}")
    print(f"R2_SECRET_ACCESS_KEY: {'*' * len(settings.R2_SECRET_ACCESS_KEY) if settings.R2_SECRET_ACCESS_KEY else 'None'}")
    print(f"R2_BUCKET: {settings.R2_BUCKET}")
    
    try:
        r2 = get_r2_storage_service()
        r2._ensure_client()
        print("\nR2 client initialized successfully.")
        
        # Test a small upload/download if we can
        test_key = "test_connection.txt"
        test_content = b"connection test"
        print(f"Attempting test upload to '{test_key}'...")
        success = r2.upload_file(test_content, test_key, "text/plain")
        if success:
            print("Upload successful!")
            print("Attempting test download...")
            downloaded = r2.get_file(test_key)
            if downloaded == test_content:
                print("Download successful! Content matches.")
            else:
                print(f"Download mismatch: {downloaded}")
            
            print("Attempting test delete...")
            r2.delete_file(test_key)
            print("Delete successful!")
        else:
            print("Upload failed.")
        
    except Exception as e:
        print(f"\nR2 test failed: {e}")

if __name__ == "__main__":
    test_r2()
