
"""
Production reset utility functions
"""
import logging
from sqlalchemy import text
from app.core.config import settings
from app.services.r2_storage import get_r2_storage_service

logger = logging.getLogger(__name__)

def run_production_reset(db):
    """
    Safely clears business data from the database and R2 storage.
    """
    logger.info("Starting production reset process...")
    
    try:
        # 1. Reset Database Tables
        tables = [
            "attendance_events", "attendance_sessions", "attendance_daily", "attendance_logs",
            "leave_transactions", "leave_balances", "leave_requests", "leave_approvals",
            "birthday_wishes", "birthday_greetings", "audit_logs", "manager_departments",
            "compoff_ledger", "compoff_requests", "wfh_requests", "hr_policy_actions",
            "company_events"
        ]
        
        for table in tables:
            try:
                db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
                logger.info(f"  Truncated table: {table}")
            except Exception as e:
                logger.warning(f"  Could not truncate {table} (it might not exist or not support CASCADE): {e}")
        
        # 2. Delete all employees except the system admin
        db.execute(text("DELETE FROM employees WHERE emp_code != 'ADM-001'"))
        logger.info("  Deleted all employees except ADM-001")
        
        db.commit()
        logger.info("DATABASE RESET SUCCESSFUL")
        
    except Exception as e:
        logger.error(f"ERROR resetting database: {e}")
        db.rollback()
        raise

    # 3. Reset Cloudflare R2
    if settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY:
        try:
            r2 = get_r2_storage_service()
            r2._ensure_client()
            
            bucket_name = settings.R2_BUCKET or "acs-hrms-storage"
            logger.info(f"  Listing objects in bucket: {bucket_name}")
            
            paginator = r2._client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name)
            
            delete_keys = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        delete_keys.append({'Key': obj['Key']})
            
            if delete_keys:
                for i in range(0, len(delete_keys), 1000):
                    batch = delete_keys[i:i + 1000]
                    r2._client.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': batch}
                    )
                    logger.info(f"  Deleted batch of {len(batch)} objects from R2.")
                logger.info("R2 STORAGE RESET SUCCESSFUL")
            else:
                logger.info("  R2 bucket is already empty.")
                
        except Exception as e:
            logger.error(f"ERROR resetting R2: {e}")
            # Don't fail the whole startup if R2 fails
    else:
        logger.info("Skipping R2 reset: Credentials not configured.")

    logger.info("--- PRODUCTION RESET COMPLETE ---")
