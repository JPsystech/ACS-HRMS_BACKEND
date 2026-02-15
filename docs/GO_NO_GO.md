# Go/No-Go Checklist

**ACS HRMS Backend - Production Readiness Checklist**

Use this checklist before deploying to production or conducting a demo.

---

## Pre-Deployment Checklist

### Environment Configuration

- [ ] **Environment Variables Set**
  - [ ] `DATABASE_URL` - PostgreSQL connection string
  - [ ] `JWT_SECRET_KEY` - At least 32 characters (required in production)
  - [ ] `APP_ENV=prod` - Set to production
  - [ ] `ALLOWED_ORIGINS` - Explicitly set (NOT "*")
  - [ ] `VERSION` - Optional version identifier
  - [ ] `LOG_LEVEL=INFO` - Appropriate for production
  - [ ] `JWT_ALGORITHM=HS256` - Default
  - [ ] `JWT_EXPIRE_MINUTES=120` - Default

- [ ] **Production Validation Passes**
  - [ ] `JWT_SECRET_KEY` length >= 32 characters
  - [ ] `ALLOWED_ORIGINS` is NOT "*"
  - [ ] `APP_ENV=prod` is set

### Database

- [ ] **Database Migrations Applied**
  - [ ] Run `alembic upgrade head` successfully
  - [ ] All migrations executed without errors
  - [ ] Database schema matches expected structure

- [ ] **Database Connection**
  - [ ] Connection string valid
  - [ ] Database accessible from application server
  - [ ] Connection pool configured appropriately

### Application Startup

- [ ] **Application Starts Successfully**
  - [ ] `uvicorn app.main:app --host 0.0.0.0 --port $PORT` runs without errors
  - [ ] No import errors
  - [ ] Logging configured correctly

- [ ] **Health Endpoints Respond**
  - [ ] `GET /api/v1/health` returns `200 OK`
  - [ ] Response includes: `status: "ok"`, `service: "acs-hrms-backend"`, `credit: "Developed & Designed by JPSystech"`
  - [ ] `GET /api/v1/version` returns `200 OK`
  - [ ] Response includes: `version`, `env: "prod"`, `credit`

---

## Core Functionality Smoke Tests

### Authentication

- [ ] **Login Works**
  - [ ] Valid credentials return `access_token`
  - [ ] Invalid credentials return `401 Unauthorized`
  - [ ] Inactive users blocked (`403 Forbidden`)

- [ ] **Authorization Works**
  - [ ] HR-only endpoints require HR role
  - [ ] Manager endpoints require appropriate role
  - [ ] Unauthorized access returns `403 Forbidden`

### Master Data

- [ ] **Department CRUD**
  - [ ] HR can create/list/update departments
  - [ ] Non-HR cannot access department endpoints

- [ ] **Employee CRUD**
  - [ ] HR can create/list/update employees
  - [ ] Password hashing works (passwords never returned)
  - [ ] Reporting hierarchy cycle prevention works

### Attendance

- [ ] **Punch-In/Out**
  - [ ] Punch-in creates attendance record
  - [ ] Duplicate punch-in same day blocked
  - [ ] Punch-out updates record
  - [ ] Punch-out without punch-in blocked

- [ ] **Attendance List**
  - [ ] HR sees all records
  - [ ] Manager sees direct reportees only
  - [ ] Employee sees own records only

### Leave Management

- [ ] **Leave Application**
  - [ ] Leave can be applied with valid dates
  - [ ] Overlap prevention works
  - [ ] Cross-year rejection works
  - [ ] Sandwich rule applies to CL/PL/SL
  - [ ] Holidays excluded from count

- [ ] **Policy Validations**
  - [ ] Probation lock blocks CL/PL
  - [ ] Notice rule blocks short notice
  - [ ] Monthly cap enforced
  - [ ] HR override works with remark

- [ ] **Leave Approval**
  - [ ] Direct reporting manager can approve
  - [ ] HR can approve any
  - [ ] Balance deduction correct
  - [ ] LWP conversion when insufficient balance
  - [ ] Reject does not change balance

### Comp-off

- [ ] **Comp-off Earn**
  - [ ] Request requires attendance + Sunday/holiday
  - [ ] Approval creates ledger credit with expiry

- [ ] **Comp-off Usage**
  - [ ] COMPOFF leave approval consumes ledger
  - [ ] Excess converts to LWP
  - [ ] Expired credits excluded from balance

### Accrual

- [ ] **Monthly Accrual**
  - [ ] Credits apply correctly
  - [ ] Caps enforced
  - [ ] Join-date rule works (<=15 vs >15)
  - [ ] Duplicate month run does not double-credit
  - [ ] Inactive employees not credited

### Reports

- [ ] **CSV Exports**
  - [ ] Attendance export works with role scoping
  - [ ] Leaves export works with overlap filter
  - [ ] Exports write audit logs

---

## Security Checklist

- [ ] **CORS Configuration**
  - [ ] CORS not wildcard in production
  - [ ] Allowed origins explicitly set

- [ ] **Error Handling**
  - [ ] Production errors do not leak internal details
  - [ ] Validation errors return user-friendly messages

- [ ] **Sensitive Data**
  - [ ] Passwords never returned in responses
  - [ ] JWT secrets not logged
  - [ ] Database credentials secure

- [ ] **Authentication**
  - [ ] JWT tokens validated correctly
  - [ ] Token expiration enforced
  - [ ] Inactive users blocked

---

## Performance & Monitoring

- [ ] **Logging**
  - [ ] Logs include request paths and status codes
  - [ ] Error logs include stack traces (development) or generic messages (production)
  - [ ] Audit logs written for critical operations

- [ ] **Database**
  - [ ] Connection pooling configured
  - [ ] Queries optimized (no N+1 issues observed)
  - [ ] Indexes present on foreign keys and frequently queried fields

---

## Known Limitations

Document any known limitations or future enhancements:

- [ ] **Accrual Scheduling**
  - Manual trigger only (no automatic cron scheduling)
  - HR must run accrual monthly via API

- [ ] **Timezone Handling**
  - Code stores UTC timestamps
  - Display timezone documented but not automatically converted

- [ ] **Comp-off Expiry**
  - Expired credits tracked but not automatically purged
  - Manual cleanup may be needed periodically

- [ ] **Report Formats**
  - CSV export only (no XLSX)
  - No pagination for large exports (may timeout)

- [ ] **Leave Cancellation**
  - No cancel endpoint (leaves can only be approved/rejected)
  - Future enhancement: allow cancellation before approval

---

## Deployment Steps Summary

### Railway Deployment

1. Create Railway project from GitHub repository
2. Add PostgreSQL database service
3. Set environment variables:
   - `DATABASE_URL` (from Railway PostgreSQL)
   - `JWT_SECRET_KEY` (generate secure key)
   - `APP_ENV=prod`
   - `ALLOWED_ORIGINS` (comma-separated frontend URLs)
   - `VERSION` (optional)
4. Set Start Command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Deploy and verify:
   - `GET /api/v1/health` returns expected response
   - `GET /api/v1/version` returns expected response

### Other Platforms

Similar steps apply:
- Set environment variables
- Run migrations (`alembic upgrade head`)
- Start application (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`)

---

## Go/No-Go Decision

### ✅ GO Criteria

- All environment variables set correctly
- Database migrations applied successfully
- Health and version endpoints respond correctly
- Core smoke tests pass
- Security checklist items verified
- Known limitations documented and acceptable

### ❌ NO-GO Criteria

- Critical functionality broken
- Security vulnerabilities identified
- Database migration failures
- Health endpoints not responding
- Sensitive data exposed
- CORS misconfigured in production

---

## Sign-off

- [ ] **Backend Engineer**: _________________ Date: _______
- [ ] **QA Engineer**: _________________ Date: _______
- [ ] **DevOps Engineer**: _________________ Date: _______

---

**Developed & Designed by JPSystech**
