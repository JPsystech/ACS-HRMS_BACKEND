# Punch-in/out with live GPS – verification

Use this to confirm that punch-in and punch-out store and return GPS (punch_in_geo, punch_out_geo), device_id, and client IP.

## Prerequisites

- Server running: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`
- Valid employee login to get `TOKEN`

## 1. Login

```bash
TOKEN=$(curl -s -X POST "http://localhost:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"emp_code":"YOUR_EMP_CODE","password":"YOUR_PASSWORD"}' | jq -r '.access_token')
echo $TOKEN
```

## 2. Punch-in with live GPS

```bash
curl -s -X POST "http://localhost:8001/api/v1/attendance/punch-in" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 28.6139,
    "lng": 77.2090,
    "accuracy": 12.5,
    "address": "Office Building A",
    "device_id": "device-xyz-001",
    "source": "MOBILE"
  }' | jq '.'
```

**Expected:** `201`, response includes:

- `work_date`, `punch_in_at`, `status`: `"OPEN"`
- `punch_in_geo`: `{ "lat": 28.6139, "lng": 77.2090, "accuracy": 12.5, "address": "Office Building A", "source": "MOBILE", ... }`
- `punch_in_device_id`: `"device-xyz-001"`
- `punch_in_ip`: client IP (or from `X-Forwarded-For`)

## 3. Punch-out with live GPS

```bash
curl -s -X POST "http://localhost:8001/api/v1/attendance/punch-out" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 28.6140,
    "lng": 77.2095,
    "accuracy": 10,
    "address": "Office Building A - Exit",
    "device_id": "device-xyz-001",
    "source": "MOBILE"
  }' | jq '.'
```

**Expected:** `200`, response includes:

- `punch_out_at`, `status`: `"CLOSED"`
- `punch_out_geo`: `{ "lat": 28.6140, "lng": 77.2095, "accuracy": 10, "address": "Office Building A - Exit", "source": "MOBILE", ... }`
- `punch_out_device_id`: `"device-xyz-001"`

## 4. Admin list (punch_in_geo / punch_out_geo in response)

As HR/ADMIN:

```bash
HR_TOKEN="<hr_or_admin_token>"
curl -s "http://localhost:8001/api/v1/admin/attendance?from=2025-01-01&to=2025-12-31" \
  -H "Authorization: Bearer $HR_TOKEN" | jq '.items[0] | { id, punch_in_geo, punch_out_geo, punch_in_device_id, punch_out_device_id, punch_in_ip, punch_out_ip }'
```

**Expected:** Each session has `punch_in_geo`, `punch_out_geo`, device IDs and IPs when provided.

## 5. Validation (optional)

- **Invalid lat:** `lat: 91` or `lat: -91` → `422` (validation error)
- **Invalid lng:** `lng: 181` → `422`
- **Invalid accuracy:** `accuracy: 0` or `accuracy: -1` → `422`
- **Mock location:** With `REJECT_MOCK_LOCATION_PUNCH=true` (default), body `"is_mocked": true` → `403` "Mock location is not allowed for punch-in"

## Config

- `REJECT_MOCK_LOCATION_PUNCH=true` (default): punch with `is_mocked: true` returns **403**.
- `REJECT_MOCK_LOCATION_PUNCH=false`: punch is allowed but session `status` is set to **SUSPICIOUS**.
