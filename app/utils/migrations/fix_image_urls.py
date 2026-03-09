from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.core.config import settings
from app.models.event import CompanyEvent
from app.models.holiday import Holiday, RestrictedHoliday
from app.utils.url_utils import build_api_image_url, normalize_public_url, is_private_host

def run() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        session = Session(bind=conn)
        try:
            evs = session.query(CompanyEvent).all()
            for ev in evs:
                if ev.image_url:
                    new = normalize_public_url(ev.image_url)
                    if new != ev.image_url:
                        ev.image_url = new
                        session.add(ev)
            hs = session.query(Holiday).all()
            for h in hs:
                if h.image_key and (not h.id):
                    pass
            rhs = session.query(RestrictedHoliday).all()
            for r in rhs:
                if r.image_key and (not r.id):
                    pass
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

if __name__ == "__main__":
    run()
