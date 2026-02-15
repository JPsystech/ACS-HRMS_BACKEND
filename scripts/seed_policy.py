"""
Seed policy for given year(s) with ACS defaults (PL=7, SL=6, CL=5, RH=1, public_holidays=14).
If policy already exists, it is left unchanged. Run from hrms-backend with .env loaded.

Usage:
  python scripts/seed_policy.py              # seeds current year and 2026
  python scripts/seed_policy.py 2026 2027   # seeds 2026 and 2027
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.services.policy_validator import get_or_create_policy_settings


def main():
    years = [2026]
    current = __import__("datetime").date.today().year
    if current not in years:
        years.append(current)
    if len(sys.argv) > 1:
        years = [int(y) for y in sys.argv[1:]]

    db = SessionLocal()
    try:
        for year in sorted(years):
            policy = get_or_create_policy_settings(db, year)
            print(f"Policy for {year}: PL={policy.annual_pl}, SL={policy.annual_sl}, CL={policy.annual_cl}, RH={policy.annual_rh}, public_holidays={policy.public_holiday_total or 14}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
