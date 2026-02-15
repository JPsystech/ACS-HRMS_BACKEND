# QA Regression Checklist

**ACS HRMS Backend - Manual Regression Testing Guide**

This document provides step-by-step manual test scenarios for validating the complete HRMS system before demo or production deployment.

**Prerequisites:**
- Backend server running (`uvicorn app.main:app --reload`)
- Database initialized and migrated (`alembic upgrade head`)
- Default HR user created (or create manually)

---

## 1. Authentication & Authorization

### 1.1 Login Flow
- [ ] **Login Success**
  - POST `/api/v1/auth/login` with valid `emp_code` and `password`
  - Verify: Returns `200 OK` with `access_token`
  - Verify: Token contains `emp_code`, `role`, `sub` (employee_id)

- [ ] **Login Failure - Wrong Password**
  - POST `/api/v1/auth/login` with valid `emp_code` but wrong `password`
  - Verify: Returns `401 Unauthorized` with error message

- [ ] **Login Failure - Inactive User**
  - Create employee with `active=false`
  - Attempt login
  - Verify: Returns `403 Forbidden` with "Account is inactive"

- [ ] **Login Failure - Invalid Employee Code**
  - POST `/api/v1/auth/login` with non-existent `emp_code`
  - Verify: Returns `401 Unauthorized`

---

## 2. Master Data Management (HR-only)

### 2.1 Department CRUD
- [ ] **Create Department (HR)**
  - Login as HR user
  - POST `/api/v1/departments` with `{"name": "Engineering", "active": true}`
  - Verify: Returns `201 Created` with department data

- [ ] **Create Department (Non-HR)**
  - Login as EMPLOYEE or MANAGER
  - POST `/api/v1/departments`
  - Verify: Returns `403 Forbidden`

- [ ] **List Departments**
  - GET `/api/v1/departments`
  - Verify: Returns list of all departments

- [ ] **Update Department**
  - PATCH `/api/v1/departments/{id}` with `{"name": "Updated Name"}`
  - Verify: Department name updated

- [ ] **Duplicate Department Name**
  - Attempt to create department with existing name
  - Verify: Returns `400 Bad Request` with duplicate error

### 2.2 Employee CRUD
- [ ] **Create Employee (HR)**
  - POST `/api/v1/employees` with:
    ```json
    {
      "emp_code": "E001",
      "name": "John Doe",
      "role": "EMPLOYEE",
      "department_id": 1,
      "join_date": "2026-01-15",
      "password": "password123"
    }
    ```
  - Verify: Returns `201 Created`, password is hashed (not returned)

- [ ] **Create Employee Without Department**
  - Attempt to create employee without `department_id`
  - Verify: Returns `400 Bad Request`

- [ ] **Duplicate Employee Code**
  - Attempt to create employee with existing `emp_code`
  - Verify: Returns `400 Bad Request`

- [ ] **Update Employee**
  - PATCH `/api/v1/employees/{id}` with updates
  - Verify: Changes reflected

- [ ] **Reset Password**
  - POST `/api/v1/employees/{id}/reset-password` with `{"new_password": "newpass123"}`
  - Verify: Password updated, old password no longer works

### 2.3 Reporting Hierarchy
- [ ] **Set Reporting Manager**
  - Create Manager (MGR001) and Employee (E001)
  - PATCH `/api/v1/employees/{E001_id}` with `{"reporting_manager_id": MGR001_id}`
  - Verify: Reporting relationship created

- [ ] **Prevent Cycle**
  - Set E001 -> MGR001
  - Attempt to set MGR001 -> E001
  - Verify: Returns `400 Bad Request` with cycle error

- [ ] **Self-Reference Prevention**
  - Attempt to set employee's `reporting_manager_id` to their own ID
  - Verify: Returns `400 Bad Request`

### 2.4 Manager-Department Assignment
- [ ] **Assign Departments to Manager**
  - POST `/api/v1/managers/{manager_id}/departments` with `{"department_ids": [1, 2]}`
  - Verify: Manager assigned to multiple departments

- [ ] **Assign to Non-Manager**
  - Attempt to assign departments to EMPLOYEE role
  - Verify: Returns `400 Bad Request`

- [ ] **List Manager Departments**
  - GET `/api/v1/managers/{manager_id}/departments`
  - Verify: Returns assigned departments

---

## 3. Attendance Management

### 3.1 Punch-In
- [ ] **Punch-In Success**
  - Login as any user
  - POST `/api/v1/attendance/punch-in` with GPS coordinates
  - Verify: Returns `200 OK` with `punch_date`, `in_time`, `in_lat`, `in_lng`

- [ ] **Duplicate Punch-In Same Day**
  - Punch-in once
  - Attempt to punch-in again same day
  - Verify: Returns `409 Conflict` with "Already punched in today"

- [ ] **Punch-In Requires Auth**
  - Call endpoint without Authorization header
  - Verify: Returns `401 Unauthorized`

### 3.2 Punch-Out
- [ ] **Punch-Out Success**
  - After punch-in, POST `/api/v1/attendance/punch-out` with GPS
  - Verify: Returns `200 OK` with `out_time`, `out_lat`, `out_lng`

- [ ] **Punch-Out Without Punch-In**
  - Attempt punch-out without prior punch-in
  - Verify: Returns `404 Not Found`

- [ ] **Double Punch-Out**
  - Punch-out once
  - Attempt punch-out again
  - Verify: Returns `409 Conflict`

### 3.3 Attendance List (Role Scoping)
- [ ] **HR Sees All**
  - Login as HR
  - GET `/api/v1/attendance/list?from=2026-01-01&to=2026-01-31`
  - Verify: Returns attendance for all employees

- [ ] **Manager Sees Direct Reportees**
  - Login as Manager with direct reportees
  - GET `/api/v1/attendance/list?from=2026-01-01&to=2026-01-31`
  - Verify: Returns only direct reportees' attendance

- [ ] **Employee Sees Own Only**
  - Login as Employee
  - GET `/api/v1/attendance/list?from=2026-01-01&to=2026-01-31`
  - Verify: Returns only own attendance records

---

## 4. Calendar Management (HR-only)

### 4.1 Holidays
- [ ] **Create Holiday**
  - Login as HR
  - POST `/api/v1/holidays` with:
    ```json
    {
      "year": 2026,
      "date": "2026-01-26",
      "name": "Republic Day",
      "active": true
    }
    ```
  - Verify: Returns `201 Created`

- [ ] **List Holidays**
  - GET `/api/v1/holidays?year=2026`
  - Verify: Returns holidays for year

- [ ] **Update Holiday**
  - PATCH `/api/v1/holidays/{id}` with updates
  - Verify: Changes reflected

- [ ] **Public Calendar Endpoint**
  - GET `/api/v1/calendars/holidays?year=2026` (no auth required)
  - Verify: Returns holidays

### 4.2 Restricted Holidays (RH)
- [ ] **Create RH**
  - POST `/api/v1/restricted-holidays` with:
    ```json
    {
      "year": 2026,
      "date": "2026-03-08",
      "name": "Women's Day",
      "active": true
    }
    ```
  - Verify: Returns `201 Created`

- [ ] **RH Single Day Only**
  - Attempt to create RH with `from_date != to_date`
  - Verify: Returns `400 Bad Request` (if validation exists)

---

## 5. Leave Management

### 5.1 Leave Application
- [ ] **Apply CL Success**
  - Login as Employee
  - POST `/api/v1/leaves/apply` with:
    ```json
    {
      "leave_type": "CL",
      "from_date": "2026-02-10",
      "to_date": "2026-02-12",
      "reason": "Personal work"
    }
    ```
  - Verify: Returns `201 Created`, `computed_days` excludes Sundays/holidays

- [ ] **Sandwich Rule - Sat-Mon**
  - Apply CL from Saturday to Monday (e.g., 2026-02-07 to 2026-02-09)
  - Verify: `computed_days` includes Sunday (sandwich rule applied)
  - Verify: `computed_days_by_month` populated correctly

- [ ] **Overlap Prevention**
  - Apply leave for Feb 10-12
  - Attempt to apply leave for Feb 11-13
  - Verify: Returns `409 Conflict` with overlap error

- [ ] **Cross-Year Rejection**
  - Attempt to apply leave from Dec 30, 2026 to Jan 2, 2027
  - Verify: Returns `400 Bad Request` with cross-year error

- [ ] **Holiday Excluded from Count**
  - Create holiday on Feb 15, 2026
  - Apply leave from Feb 14-16
  - Verify: Holiday excluded from `computed_days`

### 5.2 Policy Validations
- [ ] **Probation Lock - CL/PL Blocked**
  - Create employee joined 1 month ago (in probation)
  - Attempt to apply CL
  - Verify: Returns `403 Forbidden` with probation message

- [ ] **Probation Lock - SL Allowed**
  - Same probation employee
  - Apply SL
  - Verify: Returns `201 Created` (SL allowed during probation)

- [ ] **Notice Rule - Short Notice Blocked**
  - Apply CL with `from_date = today + 2 days` (< 3 days notice)
  - Verify: Returns `400 Bad Request` with notice error

- [ ] **Notice Rule - Sufficient Notice**
  - Apply CL with `from_date = today + 3 days` (>= 3 days notice)
  - Verify: Returns `201 Created`

- [ ] **Monthly Cap - Exceeded**
  - Approve 4 days CL/PL in same month
  - Attempt to apply 1 more day PL in same month
  - Verify: Returns `409 Conflict` with monthly cap error

- [ ] **Monthly Cap - RH Counts as PL**
  - Approve 1 day RH (counts as PL)
  - Approve 3 days PL in same month (total 4)
  - Attempt to apply 1 day CL
  - Verify: Returns `409 Conflict` (RH + PL = 4, CL would exceed)

- [ ] **HR Override**
  - Login as HR
  - Apply leave with `override_policy: true` and `override_remark: "Special case"`
  - Verify: Returns `201 Created` (policy bypassed)
  - Verify: Audit log includes override details

### 5.3 RH (Restricted Holiday) Specific
- [ ] **RH Apply Only on RH Date**
  - Create RH on March 8, 2026
  - Apply RH leave for March 8, 2026
  - Verify: Returns `201 Created`

- [ ] **RH Apply on Non-RH Date**
  - Attempt to apply RH for March 9, 2026 (not an RH date)
  - Verify: Returns `400 Bad Request`

- [ ] **RH Single Day Only**
  - Attempt to apply RH from March 8-9
  - Verify: Returns `400 Bad Request` (RH must be single day)

### 5.4 Leave Approval
- [ ] **Manager Approves Direct Reportee**
  - Employee applies leave
  - Manager (direct reporting manager) approves
  - POST `/api/v1/leaves/{leave_id}/approve` with remarks
  - Verify: Returns `200 OK`, status = APPROVED, balance deducted

- [ ] **Manager Cannot Approve Non-Reportee**
  - Employee not reporting to Manager applies leave
  - Manager attempts to approve
  - Verify: Returns `403 Forbidden`

- [ ] **HR Can Approve Any**
  - HR approves any employee's leave
  - Verify: Returns `200 OK`

- [ ] **Self-Approval Blocked**
  - Employee attempts to approve own leave
  - Verify: Returns `403 Forbidden`

- [ ] **Balance Deduction**
  - Employee has CL balance = 5.0
  - Apply CL for 3 days
  - Approve
  - Verify: `paid_days = 3.0`, `lwp_days = 0.0`, balance = 2.0

- [ ] **LWP Conversion**
  - Employee has CL balance = 1.0
  - Apply CL for 3 days
  - Approve
  - Verify: `paid_days = 1.0`, `lwp_days = 2.0`, balance = 0.0

- [ ] **Reject Does Not Change Balance**
  - Employee has CL balance = 5.0
  - Apply CL for 3 days
  - Reject
  - Verify: Balance remains 5.0

- [ ] **Approve Non-Pending Blocked**
  - Attempt to approve already-approved leave
  - Verify: Returns `400 Bad Request`

---

## 6. Comp-off Management

### 6.1 Comp-off Earn Request
- [ ] **Earn Request - Sunday with Attendance**
  - Create attendance on Sunday (both punch-in and punch-out)
  - POST `/api/v1/compoff/request` with `worked_date = Sunday`
  - Verify: Returns `201 Created`

- [ ] **Earn Request - Holiday with Attendance**
  - Create holiday on Feb 15
  - Create attendance on Feb 15
  - Request comp-off for Feb 15
  - Verify: Returns `201 Created`

- [ ] **Earn Request - Normal Weekday Rejected**
  - Create attendance on Monday
  - Attempt to request comp-off for Monday
  - Verify: Returns `400 Bad Request` (not Sunday/holiday)

- [ ] **Earn Request - No Attendance Rejected**
  - Attempt to request comp-off without attendance
  - Verify: Returns `400 Bad Request`

### 6.2 Comp-off Approval
- [ ] **Manager Approves Direct Reportee**
  - Reportee requests comp-off
  - Manager approves
  - POST `/api/v1/compoff/{request_id}/approve`
  - Verify: Returns `200 OK`, ledger CREDIT created with expiry = worked_date + 60 days

- [ ] **HR Can Approve Any**
  - HR approves any comp-off request
  - Verify: Returns `200 OK`

- [ ] **Expired Credits Excluded**
  - Create comp-off credit with `expires_on < today`
  - GET `/api/v1/compoff/balance`
  - Verify: Expired credits not counted in `available_days`

### 6.3 Comp-off Leave Usage
- [ ] **COMPOFF Leave Approval Consumes Ledger**
  - Employee has 1 day comp-off credit
  - Apply COMPOFF leave for 2 days
  - Approve
  - Verify: `paid_days = 1.0`, `lwp_days = 1.0`, ledger DEBIT created

---

## 7. Accrual Management

### 7.1 Monthly Accrual
- [ ] **Run Accrual**
  - Login as HR
  - POST `/api/v1/accrual/run?month=2026-02`
  - Verify: Returns summary with credited employees

- [ ] **Join Date Rule - <= 15th**
  - Employee joined Feb 10
  - Run accrual for February
  - Verify: Employee credited (joined <= 15th)

- [ ] **Join Date Rule - > 15th**
  - Employee joined Feb 20
  - Run accrual for February
  - Verify: Employee NOT credited
  - Run accrual for March
  - Verify: Employee credited

- [ ] **Caps Enforced**
  - Employee has CL balance = 5.8
  - Run accrual (+0.5)
  - Verify: Balance = 6.0 (capped)

- [ ] **Duplicate Month Run**
  - Run accrual for February twice
  - Verify: Second run skips already-credited employees

- [ ] **Inactive Employee Not Credited**
  - Create inactive employee
  - Run accrual
  - Verify: Inactive employee not credited

---

## 8. Reports and Exports

### 8.1 Attendance Export
- [ ] **HR Export**
  - Login as HR
  - GET `/api/v1/reports/attendance.csv?from=2026-01-01&to=2026-01-31`
  - Verify: Returns CSV with all employees' attendance

- [ ] **Manager Export**
  - Login as Manager
  - GET `/api/v1/reports/attendance.csv?from=2026-01-01&to=2026-01-31`
  - Verify: Returns CSV with only direct reportees

- [ ] **Employee Export**
  - Login as Employee
  - GET `/api/v1/reports/attendance.csv?from=2026-01-01&to=2026-01-31`
  - Verify: Returns CSV with only own records

### 8.2 Leaves Export
- [ ] **Overlap Filter**
  - Create leave from Jan 25 - Feb 5
  - Export leaves for February
  - Verify: Leave included (overlaps with February)

- [ ] **Export Writes Audit Log**
  - Export attendance
  - Check audit logs
  - Verify: `REPORT_EXPORT` entry created

---

## 9. Health and Version Endpoints

- [ ] **Health Check**
  - GET `/api/v1/health`
  - Verify: Returns `{"status": "ok", "service": "acs-hrms-backend", "credit": "Developed & Designed by JPSystech"}`

- [ ] **Version Endpoint**
  - GET `/api/v1/version`
  - Verify: Returns version, env, credit

---

## 10. Data Integrity

- [ ] **computed_days Never Negative**
  - Apply leave for valid date range
  - Verify: `computed_days > 0`

- [ ] **rh_used Never Exceeds 1**
  - Approve RH
  - Verify: `rh_used = 1`
  - Attempt to approve second RH (should be blocked)

- [ ] **Compoff Request Unique**
  - Request comp-off for same worked_date twice
  - Verify: Second request rejected (unique constraint)

---

## Notes

- All dates should be adjusted based on current date
- Use realistic test data
- Verify audit logs after critical operations
- Check error messages are user-friendly
- Ensure JPSystech credit appears in health/version endpoints

---

**Developed & Designed by JPSystech**
