from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request, Response, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.schemas.culture import BirthdayListResponse, BirthdayEmployee, GreetingRequest, ThemeResponse, WishRequest, WishOut, WishListResponse
from app.services.culture_service import list_birthdays_today, list_birthdays_upcoming, create_or_get_greeting, upload_greeting_and_update
from app.services.r2_storage import get_r2_storage_service
from app.models.birthday_greeting import BirthdayGreeting
from app.models.birthday_wish import BirthdayWish
from app.core.time_utils import now_utc, to_ist

router = APIRouter()

@router.get("/culture/birthdays/today", response_model=BirthdayListResponse)
async def birthdays_today(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    data = list_birthdays_today(db)
    items = []
    for e in data:
        dept = None
        if e.department:
            dept = e.department.name
        # Asia/Kolkata local date for birthday check
        bday = to_ist(now_utc()).date()
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
        today = to_ist(now_utc()).date()
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
async def generate_greeting(
    employee_id: int,
    payload: GreetingRequest,
    force: bool = Query(False),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    rec, created = create_or_get_greeting(db, employee_id, payload.message)
    if not rec.greeting_image_url or force:
        base_url = str(request.base_url).rstrip("/") if request is not None else None
        rec = upload_greeting_and_update(db, rec, e.name, payload.message, base_url=base_url)
    return {"id": rec.id, "greeting_image_url": rec.greeting_image_url, "created": created}

@router.post("/culture/birthday/{employee_id}/send-wish")
async def send_wish(employee_id: int, payload: WishRequest, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    today = to_ist(now_utc()).date()
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
    w = BirthdayWish(employee_id=employee_id, date=bday, sender_id=current_user.id, message=rec.wish_message)
    db.add(w)
    db.commit()
    return {"ok": True}

@router.get("/culture/theme/today", response_model=ThemeResponse)
async def theme_today(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    today = to_ist(now_utc()).date()
    if e and e.dob and e.dob.month == today.month and e.dob.day == today.day:
        name = e.name
        return ThemeResponse(mode="BIRTHDAY", bannerText=f"Happy Birthday, {name} 🎉", accent="birthday", showConfetti=True)
    return ThemeResponse(mode="NORMAL")

@router.get("/culture/birthday/{employee_id}/wishes", response_model=WishListResponse)
async def list_wishes(employee_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    today = to_ist(now_utc()).date()
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
    rows = db.query(BirthdayWish).filter(BirthdayWish.employee_id == employee_id, BirthdayWish.date == bday).order_by(BirthdayWish.created_at.desc()).all()
    items = []
    for r in rows:
        sender_name = None
        if r.sender:
            sender_name = r.sender.name
        items.append(WishOut(
            id=r.id,
            sender_id=r.sender_id,
            sender_name=sender_name,
            message=r.message,
            created_at=r.created_at.isoformat() if r.created_at else None,
            reply_message=r.reply_message,
            replied_at=r.replied_at.isoformat() if r.replied_at else None,
        ))
    if not items:
        rec = db.query(BirthdayGreeting).filter(BirthdayGreeting.employee_id == employee_id, BirthdayGreeting.date == bday).first()
        if rec and rec.wish_sent_by:
            sender = db.query(Employee).filter(Employee.id == rec.wish_sent_by).first()
            items.append(WishOut(
                id=None,
                sender_id=rec.wish_sent_by,
                sender_name=sender.name if sender else None,
                message=rec.wish_message,
                created_at=rec.wish_sent_at.isoformat() if rec.wish_sent_at else None,
                reply_message=None,
                replied_at=None,
            ))
    return WishListResponse(items=items, total=len(items))

@router.post("/culture/birthday/wishes/{wish_id}/reply")
async def reply_to_wish(
    wish_id: int,
    payload: WishRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    w = db.query(BirthdayWish).filter(BirthdayWish.id == wish_id).first()
    if not w:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wish not found")
    if w.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the birthday user can reply")
    msg = (payload.message or payload.wish_message or "").strip()
    if len(msg) < 1 or len(msg) > 250:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply must be 1..250 characters")
    w.reply_message = msg
    w.replied_at = datetime.utcnow()
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"ok": True, "wish_id": w.id, "replied_at": w.replied_at.isoformat() if w.replied_at else None}

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

@router.get("/culture/greeting-image/{employee_id}/{year}")
async def get_greeting_image(
    employee_id: int,
    year: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Serve birthday greeting image from R2 storage"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Get greeting from database
    greeting = db.query(BirthdayGreeting).filter(
        BirthdayGreeting.employee_id == employee_id,
        BirthdayGreeting.date == date(year, 1, 1)  # January 1st of the year
    ).first()
    
    if not greeting or not greeting.greeting_image_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Greeting image not found")
    
    try:
        # Construct R2 object key
        object_key = f"greetings/{employee_id}/{year}/birthday.png"
        logger.debug(f"Fetching greeting image: {object_key}")
        
        # Get image from R2
        r2_service = get_r2_storage_service()
        file_data = r2_service.get_file(object_key)
        if file_data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found in storage")
        
        # Return image with proper headers
        headers = {
            "Cache-Control": "public, max-age=86400",  # 24 hours cache
            "Content-Type": "image/png",
        }
        
        return StreamingResponse(
            iter([file_data]),
            headers=headers,
            media_type="image/png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving greeting image: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to serve image")
