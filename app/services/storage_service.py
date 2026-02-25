import os
from typing import Optional
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        self.client = None
        if self.supabase_url and self.supabase_key:
            try:
                from supabase import create_client
                self.client = create_client(self.supabase_url, self.supabase_key)
            except Exception:
                self.client = None
        self.local_dir = os.path.abspath(os.path.join(os.getcwd(), "storage"))
        os.makedirs(self.local_dir, exist_ok=True)

    def upload_bytes(self, bucket: str, path: str, data: bytes, content_type: Optional[str] = None, base_url: Optional[str] = None) -> str:
        if self.client:
            self.client.storage.from_(bucket).upload(path, data, {"contentType": content_type} if content_type else None, upsert=True)
            public_url = self.client.storage.from_(bucket).get_public_url(path)
            return public_url
        
        # For local storage: ensure path doesn't contain duplicate bucket names
        # Remove any leading bucket name from the path to avoid duplicates
        if path.startswith(f"{bucket}/"):
            path = path[len(bucket) + 1:]  # Remove "bucket/" prefix
        
        full_bucket = os.path.join(self.local_dir, bucket)
        os.makedirs(os.path.join(full_bucket, os.path.dirname(path)), exist_ok=True)
        full_path = os.path.join(full_bucket, path.replace("/", os.sep))
        with open(full_path, "wb") as f:
            f.write(data)
        
        # Return HTTP URL instead of file:// URL
        relative_path = os.path.relpath(full_path, self.local_dir)
        relative_path = relative_path.replace("\\", "/")  # Convert Windows paths to URL format
        
        # Use provided base_url or fall back to settings
        effective_base_url = base_url or settings.PUBLIC_BASE_URL
        return f"{effective_base_url}/storage/{relative_path}"
