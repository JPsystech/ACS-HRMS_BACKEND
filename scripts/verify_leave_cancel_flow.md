# Leave cancel flow – verification steps

Use this to confirm: **Apply → Approve → Cancel → GET /leaves/my** returns status **CANCELLED** (never PENDING) with **cancel_remark** and **cancelled_remark**.

## Prerequisites

- Backend running (e.g. `uvicorn app.main:app --reload --port 8001`)
- DB migrated: `alembic upgrade head`
- At least one HR user and one employee (with leave balance if applying CL/PL)

## 1. Get tokens

```bash
# Employee
EMP_TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"emp_code":"<EMP_CODE>","password":"<PASSWORD>"}' | jq -r '.access_token')

# HR
HR_TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"emp_code":"<HR_CODE>","password":"<PASSWORD>"}' | jq -r '.access_token')
```

## 2. Apply leave (employee)

```bash
curl -s -X POST http://localhost:8001/api/v1/leaves/apply \
  -H "Authorization: Bearer $EMP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"leave_type":"CL","from_date":"2026-04-01","to_date":"2026-04-01","reason":"Personal"}' | jq .
# Note: id and status (expect status "PENDING")
LEAVE_ID=<id from response>
```

## 3. Approve (HR)

```bash
curl -s -X POST "http://localhost:8001/api/v1/leaves/${LEAVE_ID}/approve" \
  -H "Authorization: Bearer $HR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"remarks":"Approved"}' | jq .
# Expect status "APPROVED"
```

## 4. Cancel (HR)

```bash
curl -s -X POST "http://localhost:8001/api/v1/hr/actions/cancel-leave/${LEAVE_ID}" \
  -H "Authorization: Bearer $HR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"recredit":false,"remarks":"Cancelled for verification"}' | jq .
# Expect 200
```

## 5. GET /leaves/my (employee) – must show CANCELLED and remark

```bash
curl -s "http://localhost:8001/api/v1/leaves/my" \
  -H "Authorization: Bearer $EMP_TOKEN" | jq '.items[] | select(.id=='$LEAVE_ID') | {id, status, reason, cancelled_remark, cancel_remark, cancelled_at, cancelled_by}'
```

**Expected:**

- `status`: `"CANCELLED"` (never PENDING)
- `reason`: `"Personal"` (unchanged)
- `cancelled_remark`: `"Cancelled for verification"`
- `cancel_remark`: same as `cancelled_remark` (for Flutter)
- `cancelled_at`, `cancelled_by` present

## 6. Optional – GET /leaves/list as HR (all leaves, no reporting_manager filter)

```bash
curl -s "http://localhost:8001/api/v1/leaves/list" \
  -H "Authorization: Bearer $HR_TOKEN" | jq '.items | length, .[0] | {id, status, cancelled_remark}'
```

HR should see all employees’ leaves; the cancelled one with `status: "CANCELLED"` and `cancelled_remark` set.

## Automated test

```bash
cd hrms-backend
python -m pytest app/tests/test_leave_cancel_flow.py -v
```

Expect: `test_apply_approve_cancel_then_fetch_shows_cancelled PASSED`.
