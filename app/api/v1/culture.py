from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from datetime import date, datetime
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.schemas.culture import BirthdayListResponse, BirthdayEmployee, GreetingRequest, ThemeResponse, WishRequest
from app.services.culture_service import list_birthdays_today, list_birthdays_upcoming, create_or_get_greeting, upload_greeting_and_update
from app.services.storage_service import StorageService
from app.models.birthday_greeting import BirthdayGreeting

router = APIRouter()

@router.get("/culture/birthdays/today", response_model=BirthdayListResponse)
async def birthdays_today(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    data = list_birthdays_today(db)
    items = []
    for e in data:
        dept = None
        if e.department:
            dept = e.department.name
        bday = date.today()
        rec = db.query(BirthdayGreeting).filter(BirthdayGreeting.employee_id == e.id, BirthdayGreeting.date == bday).first()
        wish_status = "Sent" if rec and rec.wish_sent_at else "Pending"
        items.append(BirthdayEmployee(employee_id=e.id, name=e.name, emp_code=e.emp_code, department=dept, profile_photo_url=e.profile_photo_url, dob=e.dob, birthday_date=bday, wish_status=wish_status))
    return BirthdayListResponse(items=items, total=len(items))

@router.get("/culture/birthdays/upcoming", response_model=BirthdayListResponse)
async def birthdays_upcoming(days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    data = list_birthdays_upcoming(db, days)
    items = []
    for e in data:
        dept = None
        if e.department:
            dept = e.department.name
        today = date.today()
        m = e.dob.month if e.dob else today.month
        d = e.dob.day if e.dob else today.day
        y = today.year
        try:
            bday = date(y, m, d)
        except ValueError:
            bday = date(y, 2, 28)
        if bday < today:
            ny = y + 1
            try:
                bday = date(ny, m, d)
            except ValueError:
                bday = date(ny, 2, 28)
        rec = db.query(BirthdayGreeting).filter(BirthdayGreeting.employee_id == e.id, BirthdayGreeting.date == bday).first()
        wish_status = "Sent" if rec and rec.wish_sent_at else "Pending"
        items.append(BirthdayEmployee(employee_id=e.id, name=e.name, emp_code=e.emp_code, department=dept, profile_photo_url=e.profile_photo_url, dob=e.dob, birthday_date=bday, wish_status=wish_status))
    return BirthdayListResponse(items=items, total=len(items))

@router.post("/culture/birthday/{employee_id}/generate-greeting")
async def generate_greeting(employee_id: int, payload: GreetingRequest, force: bool = Query(False), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    rec, created = create_or_get_greeting(db, employee_id, payload.message)
    if not rec.greeting_image_url or force:
        rec = upload_greeting_and_update(db, rec, e.name, payload.message)
    return {"id": rec.id, "greeting_image_url": rec.greeting_image_url, "created": created}

@router.post("/culture/birthday/{employee_id}/send-wish")
async def send_wish(employee_id: int, payload: WishRequest, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    today = date.today()
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    m = e.dob.month if e.dob else today.month
    d = e.dob.day if e.dob else today.day
    y = today.year
    try:
        bday = date(y, m, d)
    except ValueError:
        bday = date(y, 2, 28)
    rec = db.query(BirthdayGreeting).filter(BirthdayGreeting.employee_id == employee_id, BirthdayGreeting.date == bday).first()
    if not rec:
        rec = BirthdayGreeting(employee_id=employee_id, date=bday)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    rec.wish_sent_at = datetime.utcnow()
    rec.wish_sent_by = current_user.id
    msg = None
    if payload:
        msg = payload.wish_message if payload.wish_message else payload.message
    if msg:
        rec.wish_message = msg
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"ok": True}

@router.get("/culture/theme/today", response_model=ThemeResponse)
async def theme_today(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if e and e.dob and e.dob.month == date.today().month and e.dob.day == date.today().day:
        name = e.name
        return ThemeResponse(mode="BIRTHDAY", bannerText=f"Happy Birthday, {name} 🎉", accent="birthday", showConfetti=True)
    return ThemeResponse(mode="NORMAL")

@router.patch("/employees/me/profile")
async def update_profile_me(name: Optional[str] = Form(None), dob: Optional[str] = Form(None), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    if name is not None:
        e.name = name
    if dob is not None and dob.strip():
        try:
            y, m, d = dob.split("-")
            e.dob = date(int(y), int(m), int(d))
        except:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dob")
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"ok": True}

@router.post("/employees/me/photo")
async def upload_profile_photo(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    data = await file.read()
    storage = StorageService()
    path = f"profile-photos/{e.id}/avatar.jpg"
    url = storage.upload_bytes("profile-photos", path, data, file.content_type or "image/jpeg")
    e.profile_photo_url = url
    e.profile_photo_updated_at = datetime.utcnow()
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"profile_photo_url": url}
