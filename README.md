# ACS HRMS Backend

Attendance + Leave Management System Backend API

**Policy Version:** FINAL PDF Policy (Migration Patch Applied)

This system implements the FINAL Leave Policy PDF with the following key rules:
- **Annual Entitlements**: PL=7, CL=5, SL=6, RH=1
- **Monthly Credits**: +1 PL, +1 CL per month (SL is annual grant)
- **PL Eligibility**: PL allowed only after 6 months (CL allowed in joining month)
- **Backdated Leave**: Allowed up to 7 days (emergency), beyond → auto-LWP
- **Carry Forward**: Only PL, max 4 days, above → encash
- **WFH**: Max 12 days/year, counts as 0.5 day
- **Company Events**: Block leave unless HR override
- **Monthly Cap**: OFF by default (not in FINAL PDF)

See "Policy Validation Details" section below for complete policy rules.

## Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic (Migrations)
- Pytest

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL database

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

Edit `.env` and configure:
```
DATABASE_URL=postgresql://user:password@localhost:5432/acs_hrms_db
JWT_SECRET_KEY=your-secret-key-change-in-production-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=120
```

4. Initialize Alembic:
```bash
alembic init alembic
```

5. Run migrations:
```bash
cd hrms-backend
alembic upgrade head
```

**Important:** Always run Alembic commands from the `hrms-backend` directory where `alembic.ini` is located. Alembic uses the same `DATABASE_URL` as the app (from `app.core.config.settings`), so running both the app and Alembic from `hrms-backend` (with the same `.env`) ensures they use the same database file (e.g. `sqlite:///./test.db`).

**Note:** If you get `No config file 'alembic.ini' found`, ensure you're in the `hrms-backend` directory. If you see `no such table: attendance_sessions`, run `alembic upgrade head` from `hrms-backend` and confirm startup logs show the same `DATABASE_URL` path. Confirm the table exists: `python scripts/check_attendance_tables.py`.

**If you see "table departments already exists" (or similar):** Your database was created without Alembic (e.g. by `Base.metadata.create_all()`), so `alembic_version` is empty and Alembic tries to run from the first migration. Migrations 001–012 are now idempotent (they skip if tables/columns already exist), so `alembic upgrade head` should succeed. If you still hit a duplicate-table error, stamp the DB to the last revision before the new tables, then upgrade: `alembic stamp 012_approver_id` then `alembic upgrade head`.

**Optional:** Check that attendance tables exist:
```bash
cd hrms-backend
python scripts/check_attendance_tables.py
```

## Running the Application

### Development Server

```bash
cd hrms-backend
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. At startup the app logs `DATABASE_URL (app): ...` so you can confirm it matches the database used by Alembic. If you get `no such table: attendance_sessions`, run `alembic upgrade head` from `hrms-backend` (see Migrations above).

### API Documentation

- Swagger UI: `http://localhost:8000/docs` (or `http://localhost:8001/docs` if run with `--port 8001`)
- ReDoc: `http://localhost:8000/redoc`

All API routes are mounted under the prefix **`/api/v1`**. Key endpoints used by the admin dashboard and Flutter app:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login (emp_code, password) |
| GET | `/api/v1/employees` | List employees (HR-only; supports `?limit=1000`) |
| GET | `/api/v1/employees/my-team` | Current user's team (MANAGER/HR/ADMIN/MD) |
| GET | `/api/v1/leaves/pending` | Pending leave requests for approver |
| GET | `/api/v1/calendars/holidays` | Holiday calendar (`?active_only=true`, `?year=`) |
| GET | `/api/v1/attendance/list` | Attendance list (`?from=YYYY-MM-DD&to=YYYY-MM-DD`) |
| GET | `/api/v1/attendance/today` | Today's session (current user) |
| GET | `/api/v1/admin/attendance/today` | Admin: today's sessions |

**Quick curl checks** (replace `BASE=http://localhost:8001` and `TOKEN=...` after login):

```bash
# Login and get token
curl -s -X POST http://localhost:8001/api/v1/auth/login -H "Content-Type: application/json" -d '{"emp_code":"HR001","password":"your_password"}' | jq -r '.access_token'

# Then (with token set):
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/v1/employees?limit=1000"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/v1/leaves/pending"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/v1/calendars/holidays?active_only=true"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/v1/attendance/list?from=2026-01-01&to=2026-01-31"
```

## Testing

**Important:** Always run pytest from the `hrms-backend` directory (project root).

Run all tests:
```bash
cd hrms-backend
pytest
```

Run specific test file:
```bash
cd hrms-backend
pytest app/tests/test_leaves_apply.py -v
```

Run tests with verbose output:
```bash
cd hrms-backend
pytest -v
```

**Note:** If you get `ModuleNotFoundError: No module named 'app'`, ensure you're in the `hrms-backend` directory where the `app` folder is located.

### Test Coverage

The test suite covers:
- Authentication and authorization
- Master data CRUD (departments, employees, manager assignments)
- Attendance punch-in/out and role-based listing
- Leave application with policy validations
- Leave approval workflow and balance deduction
- Holiday and Restricted Holiday calendars
- Sandwich rule day calculation
- Comp-off earn and usage
- Monthly accrual engine
- Reports and CSV exports
- Data integrity and guardrails

See `docs/QA_REGRESSION_CHECKLIST.md` for manual testing scenarios.

---

## Quick Demo Flow

For a quick demonstration of the system:

1. **Setup** (if not already done):
   ```bash
   alembic upgrade head
   # Create default HR user (see Database Initialization)
   ```

2. **Start Server**:
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Login as HR**:
   ```bash
   POST /api/v1/auth/login
   {
     "emp_code": "HR001",
     "password": "hrpass123"
   }
   ```

4. **Create Department**:
   ```bash
   POST /api/v1/departments
   {
     "name": "Engineering",
     "active": true
   }
   ```

5. **Create Employee**:
   ```bash
   POST /api/v1/employees
   {
     "emp_code": "E001",
     "name": "John Doe",
     "role": "EMPLOYEE",
     "department_id": 1,
     "join_date": "2026-01-15",
     "password": "password123"
   }
   ```

6. **Punch-In** (as Employee):
   ```bash
   POST /api/v1/attendance/punch-in
   {
     "lat": 28.6139,
     "lng": 77.2090
   }
   ```

7. **Apply Leave** (as Employee):
   ```bash
   POST /api/v1/leaves/apply
   {
     "leave_type": "CL",
     "from_date": "2026-02-10",
     "to_date": "2026-02-12",
     "reason": "Personal work"
   }
   ```

8. **Approve Leave** (as Manager/HR):
   ```bash
   POST /api/v1/leaves/{leave_id}/approve
   {
     "remarks": "Approved"
   }
   ```

9. **Check Health**:
   ```bash
   GET /api/v1/health
   GET /api/v1/version
   ```

For detailed manual testing scenarios, see `docs/QA_REGRESSION_CHECKLIST.md`.
For production deployment checklist, see `docs/GO_NO_GO.md`.

## Project Structure

```
hrms-backend/
  app/
    main.py              # FastAPI application entry point
    core/                # Configuration and constants
    db/                  # Database session and base models
    api/                 # API routes
      v1/                # API version 1 endpoints
    models/              # SQLAlchemy models
    schemas/             # Pydantic schemas
    services/            # Business logic services
    policies/            # Business policies
    utils/               # Utility functions
    tests/               # Test files
  alembic/              # Database migrations
```

## API Endpoints

### Health Check

```
GET /api/v1/health
```

Response:
```json
{
  "status": "ok",
  "service": "acs-hrms-backend",
  "credit": "Developed & Designed by JPSystech"
}
```

### Authentication

#### Login

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "emp_code": "EMP001",
  "password": "password123"
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Use the `access_token` in subsequent requests:
```
Authorization: Bearer <access_token>
```

### Master Data Management (HR-only)

All master data endpoints require HR role. Non-HR users will receive 403 Forbidden.

#### Departments

- `POST /api/v1/departments` - Create department
- `GET /api/v1/departments` - List departments (with pagination)
- `GET /api/v1/departments/{id}` - Get department by ID
- `PATCH /api/v1/departments/{id}` - Update department

Example create:
```json
{
  "name": "Engineering",
  "active": true
}
```

#### Employees

- `POST /api/v1/employees` - Create employee
- `GET /api/v1/employees` - List employees (with pagination and filters)
- `GET /api/v1/employees/{id}` - Get employee by ID
- `PATCH /api/v1/employees/{id}` - Update employee
- `POST /api/v1/employees/{id}/reset-password` - Reset employee password

Example create:
```json
{
  "emp_code": "EMP001",
  "name": "John Doe",
  "role": "EMPLOYEE",
  "department_id": 1,
  "join_date": "2026-01-01",
  "password": "password123",
  "active": true,
  "reporting_manager_id": null
}
```

#### Manager-Department Assignments

- `POST /api/v1/managers/{manager_id}/departments` - Assign departments to manager
- `GET /api/v1/managers/{manager_id}/departments` - List manager's departments
- `DELETE /api/v1/managers/{manager_id}/departments/{department_id}` - Remove assignment

Example assign:
```json
{
  "department_ids": [1, 2, 3]
}
```

**Note**: Only employees with role `MANAGER` can be assigned departments.

### Attendance

#### Punch-In

- `POST /api/v1/attendance/punch-in` - Record attendance punch-in with GPS coordinates

Example punch-in:
```json
{
  "lat": 28.6139,
  "lng": 77.2090,
  "source": "mobile"
}
```

Response:
```json
{
  "id": 1,
  "employee_id": 1,
  "punch_date": "2026-01-31",
  "in_time": "2026-01-31T09:00:00Z",
  "in_lat": 28.6139,
  "in_lng": 77.2090,
  "out_time": null,
  "out_lat": null,
  "out_lng": null,
  "source": "mobile"
}
```

**Access Control:**
- Any authenticated user (EMPLOYEE, MANAGER, HR) can punch-in for themselves
- Each employee can only punch-in once per day (duplicate punch-in returns 409 Conflict)
- Punch-in requires valid JWT token

#### Punch-Out

- `POST /api/v1/attendance/punch-out` - Record attendance punch-out with GPS coordinates

Example punch-out:
```json
{
  "lat": 28.6140,
  "lng": 77.2091,
  "source": "mobile"
}
```

Response:
```json
{
  "id": 1,
  "employee_id": 1,
  "punch_date": "2026-01-31",
  "in_time": "2026-01-31T09:00:00Z",
  "in_lat": 28.6139,
  "in_lng": 77.2090,
  "out_time": "2026-01-31T18:00:00Z",
  "out_lat": 28.6140,
  "out_lng": 77.2091,
  "source": "mobile"
}
```

**Access Control:**
- Any authenticated user (EMPLOYEE, MANAGER, HR) can punch-out for themselves
- Punch-out requires existing punch-in for the same day (returns 404 if not found)
- Each employee can only punch-out once per day (duplicate punch-out returns 409 Conflict)
- Punch-out time must be after punch-in time

#### List Attendance

- `GET /api/v1/attendance/list?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD` - List attendance records with role-based scoping

**Role-Based Scoping:**
- **HR**: Can list all employees' attendance records
- **MANAGER**: Can list only employees in departments mapped to them (via `manager_departments`)
- **EMPLOYEE**: Can list only their own attendance records

Example request:
```
GET /api/v1/attendance/list?from=2026-01-01&to=2026-01-31
```

Response:
```json
{
  "items": [
    {
      "id": 1,
      "employee_id": 1,
      "punch_date": "2026-01-31",
      "in_time": "2026-01-31T09:00:00Z",
      "in_lat": 28.6139,
      "in_lng": 77.2090,
      "out_time": "2026-01-31T18:00:00Z",
      "out_lat": 28.6140,
      "out_lng": 77.2091,
      "source": "mobile"
    }
  ],
  "total": 1
}
```

**Access Control:**
- Requires valid JWT token
- Date range validation: `from_date` must be <= `to_date`
- Results are ordered by `punch_date`, then `employee_id`

#### Session-based attendance (production punch in/out)

Work date is computed in **Asia/Kolkata** timezone. One session per employee per work date (enforced in service layer).

**Employee APIs** (all roles see only their own data for `/today` and `/my`):

- `POST /api/v1/attendance/punch-in` - Body optional: `{ "source": "WEB"|"MOBILE"|"ADMIN", "punch_in_ip", "punch_in_device_id", "punch_in_geo" }`. Returns session (SessionDto). 400 if already punched in for today.
- `POST /api/v1/attendance/punch-out` - Body optional: `{ "source", "punch_out_ip", "punch_out_device_id", "punch_out_geo" }`. 400 if no active session or already punched out.
- `GET /api/v1/attendance/today` - Current user's session for today (Asia/Kolkata). Returns session or null.
- `GET /api/v1/attendance/my?from=YYYY-MM-DD&to=YYYY-MM-DD` - Current user's sessions in date range.

**Admin APIs** (HR and ADMIN; MANAGER only if they have team mapping via `manager_departments`):

- `GET /api/v1/admin/attendance/today?department_id=&status=&q=` - Today's sessions with optional filters.
- `GET /api/v1/admin/attendance?from=&to=&employee_id=&department_id=&status=` - Sessions in date range.
- `PATCH /api/v1/admin/attendance/{session_id}` - Edit punch_in_at, punch_out_at, status, remarks. Creates ADMIN_EDIT event and audit log.
- `POST /api/v1/admin/attendance/{session_id}/force-close` - Set punch_out_at=now, status=AUTO_CLOSED. Creates AUTO_OUT event.

**How to run and test:**

1. Run migrations: `alembic upgrade head` (creates `attendance_sessions` and `attendance_events`).
2. Start backend: `uvicorn app.main:app --reload` (default `http://127.0.0.1:8000`; adjust if using port 8001).
3. Login (e.g. HR or any employee), then:
   - **Punch in:** `POST /api/v1/attendance/punch-in` with `Authorization: Bearer <token>` (body `{}` or `{"source":"WEB"}`).
   - **Today:** `GET /api/v1/attendance/today`.
   - **Punch out:** `POST /api/v1/attendance/punch-out`.
4. As HR/ADMIN: `GET /api/v1/admin/attendance/today` to see today's list; PATCH a session or POST force-close. Check `attendance_events` and `audit_logs` for ADMIN_EDIT/AUTO_OUT and no JSON serialization errors (use `sanitize_for_json` for all JSON columns).

### Leave Management

#### Apply Leave

- `POST /api/v1/leaves/apply` - Apply for leave (creates PENDING request)

Example apply:
```json
{
  "leave_type": "CL",
  "from_date": "2026-02-01",
  "to_date": "2026-02-03",
  "reason": "Personal work",
  "override_policy": false,
  "override_remark": null
}
```

Example apply with HR override:
```json
{
  "leave_type": "CL",
  "from_date": "2026-02-01",
  "to_date": "2026-02-01",
  "reason": "Emergency leave",
  "override_policy": true,
  "override_remark": "HR override: Emergency situation"
}
```

**Override Fields (HR only):**
- `override_policy`: Set to `true` to override policy rules (probation, notice, monthly cap)
- `override_remark`: Mandatory remark when `override_policy` is `true`. Must be non-empty.
- Only HR role can set `override_policy=true`. Managers and employees cannot override.

Response:
```json
{
  "id": 1,
  "employee_id": 1,
  "leave_type": "CL",
  "from_date": "2026-02-01",
  "to_date": "2026-02-03",
  "reason": "Personal work",
  "status": "PENDING",
  "computed_days": 2.0,
  "applied_at": "2026-01-31T10:00:00Z",
  "created_at": "2026-01-31T10:00:00Z",
  "updated_at": "2026-01-31T10:00:00Z"
}
```

**Validations:**
- Date order: `from_date` must be <= `to_date`
- Leave year: Both dates must be in the same calendar year (Jan 1 - Dec 31)
- Overlap prevention: No overlap with existing PENDING or APPROVED leaves
- Day calculation: Uses sandwich rule for CL/PL/SL (see below)
- Leave types: CL, PL, SL, RH, COMPOFF, LWP
- COMPOFF-specific:
  - Uses comp-off ledger (not leave_balances)
  - Exempt from probation lock, notice rule, and monthly cap
  - Excess days convert to LWP if balance insufficient
- RH-specific:
  - RH must be single day (`from_date == to_date`)
  - RH date must exist in `restricted_holidays` table for that year
  - RH quota: Only one RH per employee per year (checked on apply and enforced on approval)

**Sandwich Rule (Day 9):**
- **Applies to**: CL, PL, SL only
- **Does NOT apply to**: RH, COMPOFF, LWP
- **Rule**: If leave exists on both sides of a Sunday or holiday, then that intervening Sunday/holiday is counted as leave
- **Weekly off**: Sunday only
- **Includes**: Sundays and active holidays (from `holidays` table)
- **Excludes**: Restricted Holidays (RH) are NOT included in sandwich calculations
- **Edge cases**: Sundays/holidays at the edges (without counted leave days on both sides) are NOT counted
- **Example**: Leave from Saturday to Monday → counts 3 days (Saturday + Sunday (sandwich) + Monday)
- **Month splitting**: `computed_days_by_month` field stores day counts per month ("YYYY-MM" format) for monthly cap enforcement (Day 10)

**Policy Validations (FINAL PDF):**
- **PL Eligibility**: PL allowed only after 6 months from join date. CL allowed in joining month.
- **Backdated Leave**: Allowed up to 7 days (emergency). Beyond 7 days → auto-converts to LWP.
- **Company Events**: Leave blocked on event/celebration days unless HR override.
- **Advance Notice**: Configurable (default OFF). Does NOT block backdated emergency leave.
- **Monthly Cap**: Configurable (default OFF). Not enforced unless `enforce_monthly_cap=true`.
- **HR Override**: HR can override policy rules by setting `override_policy=true` and providing a mandatory `override_remark`. Managers and employees cannot override.
- **Validation Timing**: Policy validations run at both apply-time and approval-time (unless override is enabled).

#### List Leaves

- `GET /api/v1/leaves/list?from=YYYY-MM-DD&to=YYYY-MM-DD` - List leave requests with role-based scoping

**Role-Based Scoping:**
- **HR**: Can list all employees' leave requests
- **MANAGER**: Can list only direct reportees' leave requests (employees.reporting_manager_id == manager.id)
- **EMPLOYEE**: Can list only their own leave requests

Example request:
```
GET /api/v1/leaves/list?from=2026-01-01&to=2026-12-31
```

Response:
```json
{
  "items": [
    {
      "id": 1,
      "employee_id": 1,
      "leave_type": "CL",
      "from_date": "2026-02-01",
      "to_date": "2026-02-03",
      "reason": "Personal work",
      "status": "PENDING",
      "computed_days": 2.0,
      "applied_at": "2026-01-31T10:00:00Z",
      "created_at": "2026-01-31T10:00:00Z",
      "updated_at": "2026-01-31T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Access Control:**
- Requires valid JWT token
- Date filters are optional
- Results are ordered by `applied_at` descending (most recent first)

#### Approve Leave

- `POST /api/v1/leaves/{leave_request_id}/approve` - Approve a pending leave request

**Approval Authority:**
- **HR**: Can approve any employee's leave
- **MANAGER**: Can approve only direct reportees' leave (employees.reporting_manager_id == manager.id)
- **EMPLOYEE**: Cannot approve their own leave

**Balance Deduction & LWP Conversion:**
- On approval, balance is deducted for CL/PL/SL/RH leave types
- If balance is insufficient, excess days are automatically converted to LWP
- Response includes `paid_days` (covered by balance) and `lwp_days` (converted to LWP)

**RH-Specific Rules (Day 8):**
- RH consumes PL balance (1 RH = 1 PL deducted)
- RH quota: Only one RH per employee per leave year (enforced on approval)
- If employee already has an approved RH in the same year, approval will be rejected with 409 Conflict
- RH usage is tracked in `leave_balances.rh_used` field

Example approve:
```json
{
  "remarks": "Approved"
}
```

Response:
```json
{
  "id": 1,
  "employee_id": 1,
  "leave_type": "CL",
  "from_date": "2026-02-01",
  "to_date": "2026-02-03",
  "reason": "Personal work",
  "status": "APPROVED",
  "computed_days": 3.0,
  "paid_days": 1.0,
  "lwp_days": 2.0,
  "applied_at": "2026-01-31T10:00:00Z",
  "created_at": "2026-01-31T10:00:00Z",
  "updated_at": "2026-01-31T10:00:00Z"
}
```

#### Reject Leave

- `POST /api/v1/leaves/{leave_request_id}/reject` - Reject a pending leave request

**Approval Authority:** Same as approve (HR or direct reporting manager)

Example reject:
```json
{
  "remarks": "Insufficient notice period"
}
```

**Note:** Rejection does not affect leave balances.

#### List Pending Leaves

- `GET /api/v1/leaves/pending` - List pending leave requests for approval

**Role-Based Scoping:**
- **HR**: All pending requests
- **MANAGER**: Pending requests of direct reportees only
- **EMPLOYEE**: Empty list (cannot approve)

Response:
```json
{
  "items": [
    {
      "id": 1,
      "employee_id": 1,
      "leave_type": "CL",
      "from_date": "2026-02-01",
      "to_date": "2026-02-03",
      "status": "PENDING",
      "computed_days": 3.0,
      "paid_days": 0.0,
      "lwp_days": 0.0,
      ...
    }
  ],
  "total": 1
}
```

### Holiday Calendar Management (HR-only)

#### Holidays

- `POST /api/v1/holidays` - Create holiday
- `GET /api/v1/holidays?year=YYYY` - List holidays (optionally filtered by year)
- `GET /api/v1/holidays/{id}` - Get holiday by ID
- `PATCH /api/v1/holidays/{id}` - Update holiday

Example create:
```json
{
  "year": 2026,
  "date": "2026-01-26",
  "name": "Republic Day",
  "active": true
}
```

**Validations:**
- Date must fall within the specified year
- Unique constraint: `(year, date)` - no duplicate holidays for same date in same year
- Active holidays are excluded from leave day calculation

#### Restricted Holidays (RH)

- `POST /api/v1/restricted-holidays` - Create restricted holiday
- `GET /api/v1/restricted-holidays?year=YYYY` - List restricted holidays (optionally filtered by year)
- `GET /api/v1/restricted-holidays/{id}` - Get restricted holiday by ID
- `PATCH /api/v1/restricted-holidays/{id}` - Update restricted holiday

Example create:
```json
{
  "year": 2026,
  "date": "2026-10-02",
  "name": "Gandhi Jayanti (RH)",
  "active": true
}
```

**Validations:**
- Date must fall within the specified year
- Unique constraint: `(year, date)` - no duplicate RH for same date in same year
- RH dates are used to validate RH leave applications

#### Public Calendar Endpoints (Any Authenticated User)

- `GET /api/v1/calendars/holidays?year=YYYY&active_only=true` - Get holiday calendar
- `GET /api/v1/calendars/restricted-holidays?year=YYYY&active_only=true` - Get restricted holiday calendar

These endpoints allow any authenticated user (EMPLOYEE, MANAGER, HR) to view the holiday calendars.

### Policy Settings Management (HR-only)

- `GET /api/v1/policy/{year}` - Get policy settings for a year
- `PUT /api/v1/policy/{year}` - Update policy settings for a year (creates if not exists)
- `POST /api/v1/policy/year-close?year=YYYY` - Run year-end close process (carry forward/encashment)

**Policy Settings (FINAL PDF Policy):**

**Annual Entitlements:**
- `annual_pl`: Annual PL entitlement (default: 7)
- `annual_cl`: Annual CL entitlement (default: 5)
- `annual_sl`: Annual SL entitlement (default: 6)
- `annual_rh`: Annual RH entitlement (default: 1)

**Monthly Credits:**
- `monthly_credit_pl`: Monthly PL credit (default: 1.0)
- `monthly_credit_cl`: Monthly CL credit (default: 1.0)
- `monthly_credit_sl`: Monthly SL credit (default: 0.0) - SL is annual grant, not monthly

**PL Eligibility:**
- `pl_eligibility_months`: PL allowed only after N months from join date (default: 6)
- CL is allowed in joining month (no restriction)

**Backdated Leave:**
- `backdated_max_days`: Maximum days for backdated emergency leave (default: 7)
- Beyond limit: auto-converts to LWP

**Carry Forward / Encashment:**
- `carry_forward_pl_max`: Maximum PL carry forward to next year (default: 4 in policy; can be set to 30 or per policy doc)
- Above max: encashed (year-close creates HR policy action record)

**WFH Policy:**
- `wfh_max_days`: Maximum WFH days per year (default: 12)
- `wfh_day_value`: WFH counts as N days (default: 0.5)

**Old Rules (OFF by default, not in FINAL PDF):**
- `enforce_monthly_cap`: Enable monthly cap enforcement (default: false)
- `enforce_notice_days`: Enable advance notice rule (default: false)
- `cl_pl_monthly_cap`: Monthly cap value (default: 4.0, but enforcement is OFF)
- `notice_days_cl_pl`: Notice days required (default: 3, but enforcement is OFF)

**Sandwich Rule:**
- `sandwich_enabled`: Enable sandwich rule (default: true)
- `sandwich_include_weekly_off`: Include weekly off in sandwich (default: true)
- `sandwich_include_holidays`: Include holidays in sandwich (default: true)
- `sandwich_include_rh`: Include RH in sandwich (default: false)
- `treat_event_as_non_working_for_sandwich`: Include company events in sandwich (default: true)

**HR Override:**
- `allow_hr_override`: Allow HR to override policy rules (default: true)

**Note:** Policy settings are maintained per year. If settings for a year don't exist, they are created with FINAL PDF defaults when first accessed.

### Leave Wallet / Leave Balance (ACS Policy)
- **Table**: `leave_balances` – one row per (employee_id, year, leave_type) with opening, accrued, used, remaining, carry_forward.
- **Entitlements**: CL=5, SL=6, PL=7, RH=1 (from policy settings; change via `PUT /api/v1/policy/{year}`).
- **Accrual**: +1 CL and +1 PL per month (pro-rata from join month). SL: annual grant (pro-rata for joiners). RH: 1 per year.
- **PL eligibility**: PL can be used only after 6 months from join_date (configurable `pl_eligibility_months`).
- **Carry forward**: Only PL carries to next year; cap `carry_forward_pl_max` (default 4; set to 30 if required by policy).
- **On approve**: Deduct from wallet; on reject: no deduction; on cancel (approved leave): optional recredit.
- **Endpoints**: `GET /api/v1/leaves/balance/me?year=`, `GET /api/v1/leaves/balance/summary/me?year=`, `GET /api/v1/admin/leaves/balances?year=&employee_id=&department_id=`.
- **Backfill**: Run accrual for the year or use script to ensure wallet rows for all active employees: `python scripts/backfill_leave_wallet.py --year 2026`.

### Policy Validation Details (FINAL PDF)

#### PL Eligibility Rule (Replaces Old Probation Lock)
- **Rule**: PL leave is allowed only after 6 months from join date (`join_date + 6 months`).
- **CL Rule**: CL is allowed in joining month (no restriction).
- **Allowed**: SL, COMPOFF, RH, LWP are not affected by this rule.
- **Override**: HR can override with `override_policy=true` and mandatory `override_remark`.
- **Validation**: Runs at both apply-time and approval-time.

#### Backdated Leave Rule
- **Rule**: Backdated leave allowed up to 7 days (emergency).
- **Auto-Conversion**: Beyond 7 days → automatically converts to LWP.
- **Flag**: `auto_converted_to_lwp=true` and `auto_lwp_reason` set when auto-converted.
- **Validation**: Runs at apply-time.

#### Company Event Blocking
- **Rule**: Leave not permitted on company event/celebration days (unless management approval/HR override).
- **Override**: HR override with `override_policy=true` and mandatory `override_remark` bypasses blocking.
- **Sandwich**: Company events are included in sandwich rule calculations when `treat_event_as_non_working_for_sandwich=true`.
- **Validation**: Runs at apply-time.

#### Advance Notice Rule (Configurable, Default OFF)
- **Rule**: CL and PL must be applied at least N calendar days before `from_date` (if `enforce_notice_days=true`).
- **Default**: OFF (not enforced by default, as not explicitly in FINAL PDF).
- **Backdated**: Does NOT block backdated emergency leave (handled separately).
- **Override**: HR can override with `override_policy=true` and mandatory `override_remark`.

#### Monthly Cap (Configurable, Default OFF)
- **Rule**: Total approved CL + PL + RH days cannot exceed N days per calendar month (if `enforce_monthly_cap=true`).
- **Default**: OFF (not enforced by default, as not explicitly in FINAL PDF).
- **Counting**: RH counts as PL for monthly cap calculation.
- **Override**: HR can override with `override_policy=true` and mandatory `override_remark`.

#### HR Override Mechanism
- **Authority**: Only HR role can set `override_policy=true`.
- **Requirement**: When `override_policy=true`, `override_remark` is mandatory and must be non-empty.
- **Audit**: All override usage is logged in audit logs with override details.
- **Approval**: When approving a leave request with `override_policy=true`, only HR can approve it, and `override_remark` must be present.

### Company Events Management (HR-only)

Per FINAL PDF: Company events/celebrations block leave unless management approval/HR override.

- `POST /api/v1/events` - Create company event
- `GET /api/v1/events?year=YYYY&active=true` - List company events
- `GET /api/v1/events/{id}` - Get company event by ID
- `PATCH /api/v1/events/{id}` - Update company event
- `DELETE /api/v1/events/{id}` - Delete company event

Example create:
```json
{
  "year": 2026,
  "date": "2026-12-25",
  "name": "Company Annual Day",
  "active": true
}
```

**Validations:**
- Unique constraint: `(year, date)` - no duplicate events for same date in same year
- Active events block leave applications (unless HR override)
- Events are included in sandwich rule calculations when `treat_event_as_non_working_for_sandwich=true`

### WFH (Work From Home) Management

Per FINAL PDF: Max 12 days/year, counts as 0.5 day per WFH.

- `POST /api/v1/wfh/apply` - Apply for WFH (any authenticated user)
- `GET /api/v1/wfh/my?from=YYYY-MM-DD&to=YYYY-MM-DD` - Get current user's WFH requests
- `GET /api/v1/wfh/pending` - Get pending WFH requests for approval (Manager/HR)
- `POST /api/v1/wfh/{wfh_id}/approve` - Approve WFH request (Manager direct reportees or HR)
- `POST /api/v1/wfh/{wfh_id}/reject` - Reject WFH request (Manager direct reportees or HR)

Example apply:
```json
{
  "request_date": "2026-02-15",
  "reason": "Working from home"
}
```

**Validations:**
- Yearly cap: Maximum 12 approved WFH days per year
- Day value: Each approved WFH counts as 0.5 day (configurable via policy settings)
- Approval authority: Direct reporting manager OR HR
- Cannot approve own request

### HR Policy Actions (HR-only)

Per FINAL PDF: Records penalties and administrative actions (unauthorized leave, medical cert missing, absconded, etc.).

- `POST /api/v1/hr/actions` - Create HR policy action
- `POST /api/v1/hr/actions/deduct-pl?employee_id=X&days=3` - Deduct PL as penalty (e.g., unauthorized leave)
- `POST /api/v1/hr/actions/cancel-leave/{leave_request_id}` - Cancel approved CL/PL leave (company emergency)
- `GET /api/v1/hr/actions?employee_id=X&action_type=DEDUCT_PL_3` - List HR policy actions (role-based scope)
- `GET /api/v1/hr/actions/{action_id}` - Get HR policy action by ID

Example deduct PL penalty:
```
POST /api/v1/hr/actions/deduct-pl?employee_id=5&days=3&remarks=Unauthorized leave
```

Example cancel approved leave:
```json
{
  "recredit": true,
  "remarks": "Company emergency - re-credit balance"
}
```

**Action Types:**
- `DEDUCT_PL_3`: Deduct PL as penalty (default 3 days, configurable)
- `MARK_ABSCONDED`: Mark employee as absconded (>3 days absent without info)
- `MEDICAL_CERT_MISSING_PENALTY`: Medical leave >1 day without certificate
- `CANCEL_APPROVED_LEAVE`: Company cancels approved CL/PL
- `OTHER`: Other HR administrative actions

**Note:** These actions record policy events. Payroll deduction calculations are handled separately by payroll system using `pl_encash_days` and action records.

### Year-End Close (HR-only)

Per FINAL PDF: PL carry forward (max 4) and encashment process.

- `POST /api/v1/policy/year-close?year=YYYY` - Run year-end close process

**Process:**
- For each employee:
  - Calculate unused PL at year end
  - Carry forward: min(unused_pl, 4)
  - Encash: unused_pl - carry_forward (stored in `pl_encash_days`)
  - Create next year's balance with PL = carry_forward
  - CL and SL balances reset to 0 (they lapse)

**Response:**
```json
{
  "year": 2026,
  "next_year": 2027,
  "total_employees_processed": 50,
  "employees_with_carry_forward": 30,
  "employees_with_encash": 5,
  "total_carry_forward": 120.0,
  "total_encash": 15.0,
  "details": [...]
}
```

## Database Initialization

### Local Development

1. Create database:
```bash
createdb acs_hrms_db
```

2. Run migrations:
```bash
cd hrms-backend
alembic upgrade head
```

3. (Optional) Create default HR user:
```python
from app.db.session import SessionLocal
from app.db.init_db import init_db

db = SessionLocal()
init_db(db)
db.close()
```

### Production Deployment

**Important:** Always run migrations before starting the application in production.

1. Set environment variables (see `.env.example`):
   - `DATABASE_URL`: PostgreSQL connection string
   - `JWT_SECRET_KEY`: At least 32 characters (required in production)
   - `APP_ENV=prod`: Set to production
   - `ALLOWED_ORIGINS`: Comma-separated list of allowed origins (NOT "*")
   - `VERSION`: Optional version identifier (git SHA or semver)

2. Run migrations:
```bash
alembic upgrade head
```

3. Start application:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Note:** The `$PORT` environment variable is typically provided by the hosting platform (e.g., Railway, Heroku).

This creates:
- Default HR department (if none exists)
- Default HR user: `emp_code=HR001`, `password=admin123`

**Important**: Change the default password in production!

## Authentication & Authorization

The system uses JWT tokens for authentication. Protected endpoints require:
- Valid JWT token in `Authorization: Bearer <token>` header
- Active employee account

Role-based access control is enforced using the `require_roles` dependency:
- `Role.EMPLOYEE` - Regular employees
- `Role.MANAGER` - Department managers
- `Role.HR` - HR administrators

**Access Control Rules:**
- Master data management (departments, employees, manager assignments) is **HR-only**
- Only HR can create, update, or delete departments and employees
- Only HR can assign departments to managers
- Managers and Employees have read-only access to limited self data (future enhancement)

Example protected endpoint:
```python
from app.core.deps import require_roles, get_current_user
from app.models.employee import Role

@router.get("/hr-only")
async def hr_endpoint(user: Employee = Depends(require_roles(Role.HR))):
    return {"message": "HR only"}
```

## Business Rules

### Department Management
- Department names must be unique (case-insensitive)
- Departments can be activated/deactivated via the `active` flag

### Employee Management
- Each employee must belong to exactly one department (`department_id` is required)
- Employee codes (`emp_code`) must be unique
- Reporting hierarchy:
  - An employee cannot report to themselves
  - Reporting hierarchy cannot contain cycles (e.g., A→B→A)
  - Reporting manager must have role `MANAGER` or `HR`

### Manager-Department Assignments
- Only employees with role `MANAGER` can be assigned to departments
- A manager can manage multiple departments
- Department assignments are tracked in the `manager_departments` table

## Audit Logging

All master data operations are logged in the `audit_logs` table:
- Department create/update
- Employee create/update/password reset
- Manager-department assignments

Audit logs include:
- Actor (who performed the action)
- Action type (CREATE, UPDATE, DELETE, ASSIGN)
- Entity type and ID
- Metadata (JSON)

### Accrual Management (HR-only)

- `POST /api/v1/accrual/run?month=YYYY-MM` - Run monthly accrual for a given month
- `GET /api/v1/accrual/status?year=YYYY` - Get accrual status for all employees for a year

**Monthly Accrual (FINAL PDF):**
- Credits eligible employees with:
  - +1.0 PL per month (capped at 7.0)
  - +1.0 CL per month (capped at 5.0)
  - SL is annual grant (not monthly): 6.0 days granted at first accrual run, pro-rated for mid-year joiners
- Runs monthly (manual trigger by HR, no automatic scheduling)

**Eligibility Rules:**
- Employee must be `active=true`
- **Join Date Rule (FINAL PDF):**
  - CL allowed in joining month (no restriction)
  - PL accrues monthly but cannot be used until 6 months completion
  - SL: Pro-rated annual grant based on remaining months in year
    - Example: Joined Feb → remaining months = 11 → SL = 6 * 11/12 = 5.5 days (rounded to nearest 0.5)
- **PL Eligibility**: PL accrual continues, but usage is restricted until 6 months completion.

**Caps (FINAL PDF):**
- CL balance cap: 6.0 days
- SL balance cap: 6.0 days (annual entitlement)
- PL balance cap: 7.0 days (annual entitlement)
- RH uses PL balance and has separate quota tracking (`rh_used`)

**Duplicate Prevention:**
- Uses `last_accrual_month` field to prevent double-crediting the same month
- Running accrual twice for the same month will skip already-credited employees

Example run accrual:
```
POST /api/v1/accrual/run?month=2026-02
```

Response:
```json
{
  "month": "2026-02",
  "total_employees_processed": 50,
  "credited_count": 45,
  "skipped_already_credited": 0,
  "skipped_not_eligible": 5,
  "skipped_inactive": 0,
  "details": [
    {
      "employee_id": 1,
      "emp_code": "EMP001",
      "name": "John Doe",
      "cl_balance": 2.5,
      "sl_balance": 1.5,
      "pl_balance": 3.0
    }
  ],
  "credit": "Developed & Designed by JPSystech"
}
```

**Note:** Accrual engine is implemented (Day 11). Manual HR endpoint provided; automatic scheduling can be added later.

### Comp-off Management

- `POST /api/v1/compoff/request` - Request comp-off earn (any authenticated user)
- `GET /api/v1/compoff/my-requests` - List own comp-off requests
- `GET /api/v1/compoff/balance` - Get comp-off balance for current user
- `GET /api/v1/compoff/pending` - List pending comp-off requests for approval
- `POST /api/v1/compoff/{request_id}/approve` - Approve comp-off earn request
- `POST /api/v1/compoff/{request_id}/reject` - Reject comp-off earn request

**Eligibility to Earn Comp-off:**
- Employee must have attendance (both punch-in and punch-out) on `worked_date`
- `worked_date` must be Sunday OR an active holiday (from `holidays` table)
- One earn request per day per employee (unique constraint)

**Comp-off Earn Request Flow:**
1. Employee requests comp-off for a worked date (Sunday/holiday)
2. Request status: PENDING
3. Direct reporting manager or HR approves/rejects
4. On approval: Creates ledger CREDIT entry (1.0 day) with expiry (worked_date + 60 days)
5. On rejection: Request status changes to REJECTED, no ledger entry

**Comp-off Balance:**
- Available days = sum(credits not expired) - sum(debits)
- Credits expire 60 days from `worked_date`
- Expired credits are excluded from available balance

**Using Comp-off as Leave:**
- Apply leave with `leave_type: "COMPOFF"`
- On approval:
  - Available comp-off days are deducted from ledger (DEBIT entry created)
  - Excess days are converted to LWP (similar to other leave types)
  - Example: 2 days requested, 1 day available → paid_days=1, lwp_days=1

**Approval Authority:**
- HR can approve/reject any employee's comp-off request
- MANAGER can approve/reject only direct reportees' comp-off requests
- Employee cannot approve/reject their own comp-off request

**Policy Exemptions:**
- COMPOFF is exempt from probation lock (can be used during probation)
- COMPOFF is exempt from advance notice rule
- COMPOFF is exempt from monthly cap (CL+PL+RH cap)

Example request comp-off:
```json
{
  "worked_date": "2026-02-09",
  "reason": "Worked on Sunday"
}
```

Example balance response:
```json
{
  "employee_id": 1,
  "available_days": 2.0,
  "credits": 3.0,
  "debits": 1.0,
  "expired_credits": 0.0
}
```

**Note:** Comp-off module is implemented (Day 12). Ledger-based approach with expiry tracking and integration with leave approval.

### Reports and Exports

- `GET /api/v1/reports/attendance.csv` - Export attendance data as CSV
- `GET /api/v1/reports/leaves.csv` - Export leave data as CSV
- `GET /api/v1/reports/compoff.csv` - Export comp-off request data as CSV

**Role-based Scoping:**
- HR: Can export all employees/departments
- MANAGER: Can export only direct reportees (consistent with approval authority)
- EMPLOYEE: Can export only own records

**Query Parameters:**

**Attendance Export:**
- `from` (required): Start date (YYYY-MM-DD)
- `to` (required): End date (YYYY-MM-DD)
- `employee_id` (optional): Filter by employee ID (role-restricted)
- `department_id` (optional): Filter by department ID (HR only)

**Leaves Export:**
- `from` (required): Start date (YYYY-MM-DD)
- `to` (required): End date (YYYY-MM-DD)
- `employee_id` (optional): Filter by employee ID (role-restricted)
- `department_id` (optional): Filter by department ID (HR only)
- `status` (optional): Filter by status (PENDING, APPROVED, REJECTED)
- `leave_type` (optional): Filter by leave type (CL, PL, SL, RH, COMPOFF, LWP)

**Comp-off Export:**
- `from` (required): Start date (YYYY-MM-DD)
- `to` (required): End date (YYYY-MM-DD)
- `employee_id` (optional): Filter by employee ID (role-restricted)

**Date Overlap Logic (Leaves):**
- Includes leaves that overlap with the date range (not just starts within range)
- Formula: `leave.to_date >= filter_from AND leave.from_date <= filter_to`

**CSV Format:**
- UTF-8 encoded
- Headers included
- Proper quoting for special characters
- Filename includes date range (e.g., `attendance_20260101_20260131.csv`)

**Audit Logging:**
- All exports trigger audit log entry with action `REPORT_EXPORT`
- Meta includes: report_type, from_date, to_date, filters, row_count

Example URLs:
```
GET /api/v1/reports/attendance.csv?from=2026-01-01&to=2026-01-31
GET /api/v1/reports/leaves.csv?from=2026-01-01&to=2026-01-31&status=APPROVED&leave_type=CL
GET /api/v1/reports/compoff.csv?from=2026-01-01&to=2026-01-31&employee_id=5
```

**Note:** Reports module is implemented (Day 13). CSV streaming with role-based scoping and comprehensive audit logging.

## Production Deployment

### Railway Deployment Guide

Railway is a modern platform for deploying applications. Follow these steps to deploy the ACS HRMS Backend:

#### Prerequisites
- GitHub account with the repository
- Railway account (sign up at https://railway.app)

#### Step 1: Create Railway Project

1. Log in to Railway dashboard
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account and select the repository
5. Railway will automatically detect the project

#### Step 2: Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will create a PostgreSQL instance and provide `DATABASE_URL` automatically

#### Step 3: Configure Environment Variables

In Railway project settings, add the following environment variables:

**Required:**
- `DATABASE_URL`: Automatically provided by Railway PostgreSQL service (use the variable reference)
  - **Format examples:**
    - `postgresql+psycopg2://user:password@host:port/database`
    - `postgresql+psycopg://user:password@host:port/database`
  - **On Render**: Use the Internal Database URL if using Render Postgres, or External URL for other providers
- `JWT_SECRET_KEY`: Generate a secure random string (minimum 32 characters)
  ```bash
  # Generate a secure key:
  openssl rand -hex 32
  ```

**Production Settings:**
- `APP_ENV=prod`: Set to production environment
- `ALLOWED_ORIGINS`: Comma-separated list of your frontend URLs
  ```
  Example: https://yourdomain.com,https://app.yourdomain.com
  ```
  **Important:** Do NOT use `*` in production

**Optional:**
- `VERSION`: Git SHA or semantic version (e.g., `1.0.0`)
- `LOG_LEVEL=INFO`: Logging level
- `TZ=Asia/Kolkata`: Timezone (for documentation; code uses UTC)
- `JWT_ALGORITHM=HS256`: JWT algorithm (default)
- `JWT_EXPIRE_MINUTES=120`: Token expiration (default)

#### Step 4: Configure Start Command

In Railway project settings → "Settings" → "Deploy", set the Start Command:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

This will:
1. Run database migrations (`alembic upgrade head`)
2. Start the FastAPI application on the port provided by Railway

#### Step 5: Deploy

1. Railway will automatically deploy on every push to the main branch
2. Monitor the deployment logs in Railway dashboard
3. Once deployed, Railway will provide a service URL (e.g., `https://your-app.railway.app`)

#### Step 6: Verify Deployment

Test the deployment:

1. **Health Check:**
   ```bash
   curl https://your-app.railway.app/api/v1/health
   ```
   Expected response:
   ```json
   {
     "status": "ok",
     "service": "acs-hrms-backend",
     "credit": "Developed & Designed by JPSystech"
   }
   ```

2. **Version Endpoint:**
   ```bash
   curl https://your-app.railway.app/api/v1/version
   ```
   Expected response:
   ```json
   {
     "service": "acs-hrms-backend",
     "version": "1.0.0",
     "env": "prod",
     "credit": "Developed & Designed by JPSystech"
   }
   ```

#### Step 7: Configure Custom Domain (Optional)

1. In Railway project → "Settings" → "Domains"
2. Add your custom domain
3. Configure DNS records as instructed by Railway

### Other Deployment Platforms

The application can be deployed on any platform that supports Python and PostgreSQL:

- **Heroku**: Similar to Railway, use Procfile and environment variables
- **AWS Elastic Beanstalk**: Use `.ebextensions` for configuration
- **Google Cloud Run**: Use Dockerfile and Cloud Build
- **DigitalOcean App Platform**: Similar to Railway
- **Self-hosted**: Use systemd service or Docker Compose

### Production Checklist

Before deploying to production, ensure:

- [ ] `APP_ENV=prod` is set
- [ ] `JWT_SECRET_KEY` is at least 32 characters
- [ ] `ALLOWED_ORIGINS` is explicitly set (not "*")
- [ ] `DATABASE_URL` points to production database
- [ ] Database migrations have been run (`alembic upgrade head`)
- [ ] All environment variables are set correctly
- [ ] Health and version endpoints are accessible
- [ ] CORS is configured correctly for your frontend domain
- [ ] Logging is configured appropriately (`LOG_LEVEL=INFO` recommended)

### Security Considerations

- **Never commit `.env` file** to version control
- **Use strong JWT_SECRET_KEY** (minimum 32 characters, random)
- **Restrict CORS origins** in production (never use "*")
- **Use HTTPS** in production (Railway provides this automatically)
- **Regular database backups** (Railway provides automatic backups)
- **Monitor logs** for suspicious activity
- **Keep dependencies updated** (`pip install --upgrade -r requirements.txt`)

### Monitoring and Logs

- Railway provides built-in log viewing in the dashboard
- Logs include request paths, status codes, and errors
- Set `LOG_LEVEL=DEBUG` for detailed logging (development only)
- Production should use `LOG_LEVEL=INFO` or `WARNING`

## Documentation

- **QA Regression Checklist**: `docs/QA_REGRESSION_CHECKLIST.md` - Manual testing scenarios
- **Go/No-Go Checklist**: `docs/GO_NO_GO.md` - Production readiness checklist

## Support

For issues or questions, refer to:
- API Documentation: `http://localhost:8000/docs` (Swagger UI)
- ReDoc: `http://localhost:8000/redoc`

---

**Developed & Designed by JPSystech**

---

## Policy Migration Notes

**Migration Applied:** Policy Migration Patch (Revision 011)

This migration updates the system from the previous policy to match the FINAL PDF Policy:

**Key Changes:**
- **Accrual**: Changed from +0.5 monthly to +1 PL and +1 CL monthly
- **SL**: Changed from monthly accrual to annual grant (pro-rated for mid-year joiners)
- **Caps**: Updated to match PDF (CL=5, SL=6, PL=7)
- **PL Eligibility**: Replaced 3-month probation lock with 6-month PL eligibility rule
- **CL**: Now allowed in joining month (no restriction)
- **Backdated Leave**: New rule - 7 days max, auto-LWP beyond
- **Carry Forward**: New feature - PL carry forward (max 4) and encashment
- **WFH**: New module - 12 days/year, 0.5 day value
- **Company Events**: New feature - blocks leave unless HR override
- **Monthly Cap**: Disabled by default (not in FINAL PDF)
- **Notice Rule**: Disabled by default (configurable, does not block backdated emergency)

**Assumptions Made:**
- SL annual grant is pro-rated for mid-year joiners: `annual_sl * remaining_months / 12`
- PL carry forward applies only to next 1 year (simplified implementation)
- Company events are treated as non-working for sandwich rule when enabled
- Backdated leave auto-conversion happens at apply-time (deterministic)
- HR override requires HR role and mandatory remark (enforced)
- WFH rejection does not auto-convert to leave (approver/HR decides separately)

**Database Changes:**
- New tables: `company_events`, `wfh_requests`, `hr_policy_actions`
- New columns in `policy_settings`: Annual entitlements, monthly credits, PL eligibility, backdated rules, carry forward, WFH settings
- New columns in `leave_balances`: `pl_carried_forward`, `pl_encash_days`
- New columns in `leave_requests`: `auto_converted_to_lwp`, `auto_lwp_reason`
- New status: `CANCELLED_BY_COMPANY` in `LeaveStatus` enum

**Migration Command:**
```bash
cd hrms-backend
alembic upgrade head
```

This will apply migration `011_policy_migration` which includes all database changes and backfills existing policy_settings with new defaults.
