from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.employee import Employee
from app.models.birthday_greeting import BirthdayGreeting
from app.services.storage_service import StorageService
from typing import Optional
from app.utils.datetime_utils import now_utc, to_ist

def list_birthdays_today(db: Session) -> List[Tuple[Employee]]:
    items = db.query(Employee).filter(Employee.dob.isnot(None), Employee.active == True).all()
    today = to_ist(now_utc()).date()
    result = []
    for e in items:
        if e.dob and e.dob.month == today.month and e.dob.day == today.day:
            result.append(e)
    return result

def list_birthdays_upcoming(db: Session, days: int) -> List[Employee]:
    items = db.query(Employee).filter(Employee.dob.isnot(None), Employee.active == True).all()
    today = to_ist(now_utc()).date()
    upcoming = []
    for e in items:
        if not e.dob:
            continue
        m = e.dob.month
        d = e.dob.day
        y = today.year
        if m == 2 and d == 29:
            try:
                b = date(y, 2, 29)
            except ValueError:
                b = date(y, 2, 28)
        else:
            b = date(y, m, d)
        delta = (b - today).days
        if delta < 0:
            ny = today.year + 1
            if m == 2 and d == 29:
                try:
                    b = date(ny, 2, 29)
                except ValueError:
                    b = date(ny, 2, 28)
            else:
                b = date(ny, m, d)
            delta = (b - today).days
        if 0 < delta <= days:
            upcoming.append((delta, e))
    upcoming.sort(key=lambda x: x[0])
    return [e for _, e in upcoming]

def ensure_buckets():
    pass

def generate_greeting_image(name: str, message: Optional[str] = None) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (1200, 630), (255, 240, 245, 255))
        draw = ImageDraw.Draw(img)
        title = "Happy Birthday"
        subtitle = name
        try:
            font1 = ImageFont.truetype("arial.ttf", 64)
            font2 = ImageFont.truetype("arial.ttf", 48)
        except:
            font1 = ImageFont.load_default()
            font2 = ImageFont.load_default()
        w1, h1 = draw.textsize(title, font=font1)
        w2, h2 = draw.textsize(subtitle, font=font2)
        draw.text(((1200 - w1) / 2, 200), title, fill=(220, 20, 60), font=font1)
        draw.text(((1200 - w2) / 2, 300), subtitle, fill=(50, 50, 50), font=font2)
        if message and message.strip():
            try:
                font3 = ImageFont.truetype("arial.ttf", 36)
            except:
                font3 = ImageFont.load_default()
            w3, h3 = draw.textsize(message, font=font3)
            draw.text(((1200 - w3) / 2, 380), message, fill=(80, 80, 80), font=font3)
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return b""

def create_or_get_greeting(db: Session, employee_id: int, message: Optional[str]) -> Tuple[BirthdayGreeting, bool]:
    today = to_ist(now_utc()).date()
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if e and e.dob:
        m = e.dob.month
        d = e.dob.day
        y = today.year
        try:
            bday = date(y, m, d)
        except ValueError:
            bday = date(y, 2, 28)
    else:
        bday = today
    existing = db.query(BirthdayGreeting).filter(and_(BirthdayGreeting.employee_id == employee_id, BirthdayGreeting.date == bday)).first()
    if existing:
        return existing, False
    rec = BirthdayGreeting(employee_id=employee_id, date=bday, greeting_message=message)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec, True

def upload_greeting_and_update(
    db: Session,
    greeting: BirthdayGreeting,
    name: str,
    message: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BirthdayGreeting:
    content = generate_greeting_image(name, message)
    storage = StorageService()
    year = greeting.date.year
    path = f"greetings/{greeting.employee_id}/{year}/birthday.png"
    url = storage.upload_bytes("greetings", path, content, "image/png", base_url=base_url)
    greeting.greeting_image_url = url
    db.add(greeting)
    db.commit()
    db.refresh(greeting)
    return greeting
